import os
import asyncio

from store.messages_store import MessagesStore
from store.message_entity import MessageEntity

from dotenv import load_dotenv
load_dotenv()

class EchoService:

    def __init__(self, messages_store):        
        self.messages_store = messages_store


    async def send_echo_message(self, message: MessageEntity):

        await self.messages_store.store(
            role="echo",
            gateway=message.gateway,
            direction="outgoing",

            text_content=message.text_content,
            file_content=message.file_content,

            external_chat_id=message.external_chat_id,
            # external_user_id=message.external_user_id,
            # external_user_name=message.external_user_name,
            # external_message_id=message.external_message_id
        )


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="incoming",
            listener=self.send_echo_message
        )


async def main() -> None:

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    echo_service = EchoService(
        messages_store=messages_store
    )

    await echo_service.run()


if __name__ == "__main__":
    asyncio.run(main())
