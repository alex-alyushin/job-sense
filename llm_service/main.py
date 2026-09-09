import os
import json
import asyncio
import logging

from openai import OpenAI
from openai.types.responses import Response, ResponseInputParam

from psycopg import AsyncCursor

from store.entities.message_entity import MessageEntity
from store.entities.user_entity import UserEntity
from store.messages_store import MessagesStore

from embedding.embedder import Embedder

from utils.utils import truncate
from utils.log import configure_logging

from .system_prompts.system_prompt_v3 import system_prompt_v3

from .complete import LLMCompletionService

from .tools import TOOLS

ALLOWED_ROLES = [
    "assistant",
    "system",
    "developer",
    "user"
]

class LLMService:

    def __init__(self, openai_token: str, openai_model: str, messages_store: MessagesStore):
        self.logger = logging.getLogger("llm_service")
        self.logger.setLevel(logging.INFO)

        self.openai_client = OpenAI(api_key=openai_token)
        self.openai_model = openai_model

        self.messages_store = messages_store

        self.embedder = Embedder()


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="assistant",
            listener=self.ask
        )


    ##################
    # STORE LISTENER #
    ##################

    async def ask(self, cursor: AsyncCursor, message: MessageEntity):

        # 1. Ensure user

        user: UserEntity = await self.messages_store.ensure_user(cursor, message=message)

        if user is None:
            self.logger.error("[LLM][ERROR] User not found")
            return

        # 2. Load LLM history

        messages = await self.messages_store.load_latest_messages(
            cursor, chat_id=user.external_chat_id,
        )

        history = self._llm_history(messages=messages)

        # debug
        self._log_llm_history(history)

        # 3. Ask LLM

        response = self.openai_client.responses.create(
            model=self.openai_model,
            input=history,
            tools=TOOLS,
            tool_choice="auto",
        )

        # 4. Immediately send LLM response to User

        for index, item in enumerate(response.output):

            text_content = ""

            if item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        text_content = text_content + content.text

            if text_content:
                await self.messages_store.store(
                    role="assistant",
                    gateway=message.gateway,
                    direction="user",
                    text_content=text_content,
                    external_chat_id=message.external_chat_id,
                    external_user_id=message.external_user_id,
                    external_user_name=message.external_user_name,
                    llm_response=item.model_dump(),
                    attributes={
                        "llm_model": self.openai_model,
                        "llm_usage": response.usage.model_dump(),
                    } if index == 0 else None
                )

        # 5. Tools calling

        for item in response.output:
            if item.type != "function_call":
                continue

            if item.name == "store_user_cv":
                await self._store_user_cv_impl(
                    cursor,
                    call_id=item.call_id,
                    arguments=item.arguments,
                    user=user
                )

            elif item.name == "search_linkedin_jobs":
                await self._search_linkedin_jobs_impl(
                    call_id=item.call_id,
                    arguments=item.arguments,
                    user=user
                )

            else:
                raise ValueError(f"Unknown function: {item.name}")


    def _llm_history(self, *, messages: list[MessageEntity]) -> list[ResponseInputParam]:

        function_calls = set()
        function_call_outputs = set()

        llm_history: list[tuple[
            ResponseInputParam | None,  # item
            bool,                       # is_processed
        ]] = []

        # 1. Restore LLM History
        
        llm_history.append((
            {
                "role": "developer",
                "content": system_prompt_v3,
                "type": "message",
            },
            True,
        ))

        for message in messages:

            item = None

            if message.role == "user":
                content = ""

                if message.text_content:
                    content += message.text_content + "\n\n"

                if message.file_content:
                    if message.file_name:
                        content += f"{message.file_name}:\n"
                    content += message.file_content

                item = {
                    "role": "user",
                    "content": content,
                    "type": "message",
                }

            if message.role == "assistant":
                item = message.llm_response

                item_type = item.get("type") or ""
                call_id = item.get("call_id") or ""

                if call_id and item_type == "function_call":
                    function_calls.add(call_id)

                if call_id and item_type == "function_call_output":
                    function_call_outputs.add(call_id)

            llm_history.append((
                item,
                message.processed_at is not None,
            ))

        # 2. Match Function Calls and Outputs

        for index, (item, _) in enumerate(llm_history):
            if item is None:
                continue
    
            item_type = item.get("type") or ""
            call_id = item.get("call_id") or ""

            if item_type == "function_call":
                if call_id not in function_call_outputs:
                    llm_history[index] = (None, False)

            if item_type == "function_call_output":
                if call_id not in function_calls:
                    llm_history[index] = (None, False)

        # 3. Check for New Input

        has_updates = False

        for (item, is_processed) in llm_history:
            if item is None:
                continue

            if is_processed:
                continue

            item_type = item.get("type") or ""
            item_role = item.get("role") or ""

            if item_role == "user" or item_type == "function_call_output":
                has_updates = True
                break
        
        if not has_updates:
            return []

        return [
            item
            for (item, _) in llm_history
            if item is not None
        ]


    def _log_llm_history(self, history: list[ResponseInputParam]):
        self.logger.info("[HISTORY] count = %d", len(history))

        for index, item in enumerate(history):
            self.logger.info(
                "[HISTORY] %-2d: %s",
                index + 1, repr(item)[:128],
            )


    #######################
    # TOOL: Store User CV #
    #######################

    # todo: create new UserCVService

    async def _store_user_cv_impl(
        self, cursor, *,
        call_id: str,
        arguments: str,
        user: UserEntity,
    ) -> dict:

        await self.messages_store.store(
            role="assistant",
            gateway=user.gateway,
            direction="assistant",
            external_chat_id=user.external_chat_id,
            external_user_id=user.external_user_id,
            external_user_name=user.external_user_name,
            llm_response={
                "type": "function_call",
                "name": "store_user_cv",
                "arguments": arguments,
                "call_id": call_id,
            }
        )

        cv_content=json.loads(arguments)["content"]
        cv_embedding = self.embedder.encode(text=cv_content)

        stored_cv = await self.messages_store.store_user_cv(
            cursor,
            content=cv_content,
            embedding=cv_embedding,
            user=user,
        )

        tool_result = {"status": "ok" if (stored_cv is not None) else "err"}

        # assistant -> (next iteration) assistant
        await self.messages_store.store(
            role="assistant",
            gateway=user.gateway,
            direction="assistant",
            external_chat_id=user.external_chat_id,
            external_user_id=user.external_user_id,
            external_user_name=user.external_user_name,
            llm_response={
                "type": "function_call_output",
                "output": json.dumps(tool_result),
                "call_id": call_id,
            }
        )


    ###############################
    # TOOL: Search LinkedIn Jobs  #
    ###############################

    async def _search_linkedin_jobs_impl(
        self, *,
        call_id: str,
        arguments: str,
        user: UserEntity,
    ) -> dict:

        await self.messages_store.store(
            role="assistant",
            gateway=user.gateway,
            direction="searcher",
            external_chat_id=user.external_chat_id,
            external_user_id=user.external_user_id,
            external_user_name=user.external_user_name,
            llm_response={
                "type": "function_call",
                "name": "search_linkedin_jobs",
                "arguments": arguments,
                "call_id": call_id,
            }
        )


async def create_messages_store() -> MessagesStore:
    return await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )


async def main() -> None:

    from dotenv import load_dotenv
    load_dotenv()

    configure_logging(service_name="LLMService")

    openai_token = os.getenv("OPENAI_TOKEN")
    openai_model = os.getenv("OPENAI_MODEL")

    # Each listener holds the connection it waits for notifications on, so
    # the two channels need a store each.

    llm_service = LLMService(
        openai_token=openai_token,
        openai_model=openai_model,
        messages_store=await create_messages_store()
    )

    completion_service = LLMCompletionService(
        openai_token=openai_token,
        openai_model=openai_model,
        messages_store=await create_messages_store()
    )

    await asyncio.gather(
        llm_service.run(),
        completion_service.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
