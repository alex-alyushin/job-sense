import os
import json
import asyncio

from openai import OpenAI

from store.messages_store import MessagesStore
from store.message_entity import MessageEntity

from prompts.system_prompt_v0 import system_prompt_v0
from prompts.system_prompt_v1 import system_prompt_v1

from dotenv import load_dotenv
load_dotenv()

class LLMService:

    def __init__(self, openai_token: str, openai_model: str, messages_store: MessagesStore):
        self.openai_client = OpenAI(api_key=openai_token)
        self.openai_model = openai_model
        self.messages_store = messages_store


    async def _load_llm_history(self, chat_id):

        messages = await self.messages_store.load_unresolved_messages(
            chat_id=chat_id
        )

        llm_history = [
            {
                "role": "developer",
                "content": system_prompt_v1
            },
        ]

        for message in messages:
            content = ""

            if message.text_content is not None:
                content = content + message.text_content + "\n\n"

            if message.file_content is not None:
                content = content + f"My Resume here:\n\n{message.file_content}"

            llm_history.append({
                "role": message.role,
                "content": content
            })

        return llm_history


    def _ask_llm(self, llm_input):
        return self.openai_client.responses.create(
            model=self.openai_model,
            input=llm_input
        )


    async def _send_message(
        self,
        gateway,
        direction,
        text_content,
        external_chat_id
    ):
        await self.messages_store.store(
            role="assistant",
            gateway=gateway,
            direction=direction,
            text_content=text_content,
            external_chat_id=external_chat_id,
        )


    async def send_message_to_llm(self, message: MessageEntity):

        llm_input = await self._load_llm_history(chat_id=message.external_chat_id)

        llm_response = self._ask_llm(llm_input=llm_input)

        try:
            search_params = json.loads(llm_response.output_text)

            await self._send_message(
                direction="internal",
                gateway=message.gateway,
                text_content=json.dumps(search_params),
                external_chat_id=message.external_chat_id,
            )

        except json.JSONDecodeError:
            await self._send_message(
                direction="outgoing",
                gateway=message.gateway,
                text_content=llm_response.output_text,
                external_chat_id=message.external_chat_id,
            )


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="incoming",
            listener=self.send_message_to_llm
        )


async def main() -> None:

    openai_token = os.getenv("OPENAI_TOKEN")
    openai_model = os.getenv("OPENAI_MODEL")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
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
