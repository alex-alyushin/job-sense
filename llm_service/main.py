import os
import asyncio

from openai import OpenAI

from store.messages_store import MessagesStore, AsyncCursor
from store.message_entity import MessageEntity

from .system_prompt_v0 import system_prompt_v0
from .system_prompt_v1 import system_prompt_v1
from .system_prompt_v2 import system_prompt_v2

from utils.utils import is_json
from utils.log import configure_logging

ALLOWED_ROLES = [
    "assistant",
    "system",
    "developer",
    "user"
]


class LLMService:

    def __init__(self, openai_token: str, openai_model: str, messages_store: MessagesStore):
        self.openai_client = OpenAI(api_key=openai_token)
        self.openai_model = openai_model
        self.messages_store = messages_store


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="incoming",
            listener=self.ask
        )


    ##################
    # STORE LISTENER #
    ##################

    async def ask(self, cursor: AsyncCursor, message: MessageEntity):

        # 1. Load LLM history

        messages = await self.messages_store.load_unresolved_messages(
            cursor,
            chat_id=message.external_chat_id
        )

        history = [{
            "role": "developer",
            "content": system_prompt_v2
        }]

        for item in messages:
            content = ""

            if item.role not in ALLOWED_ROLES:
                continue

            if item.text_content is not None:
                content = content + item.text_content + "\n\n"

            if item.file_content is not None:
                # @todo: remove dependency from job search
                content = content + f"My Resume here:\n\n{item.file_content}"

            history.append({
                "role": item.role,
                "content": content
            })

        # 2. Ask LLM

        response = self.openai_client.responses.create(
            model=self.openai_model,
            input=history
        )

        # 3. Store response

        response_direction = "outgoing"
        if is_json(response.output_text):
            response_direction = "internal"

        await self.messages_store.store(
            role="assistant",
            gateway=message.gateway,
            direction=response_direction,
            text_content=response.output_text,
            external_chat_id=message.external_chat_id,
            attributes={
                "llm_model": self.openai_model,
                "llm_usage": response.usage.model_dump(),
            }
        )


async def main() -> None:

    from dotenv import load_dotenv
    load_dotenv()

    configure_logging(service_name="LLMService")

    openai_token = os.getenv("OPENAI_TOKEN")
    openai_model = os.getenv("OPENAI_MODEL")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    llm_service = LLMService(
        openai_token=openai_token,
        openai_model=openai_model,
        messages_store=messages_store
    )

    await llm_service.run()


if __name__ == "__main__":
    asyncio.run(main())
