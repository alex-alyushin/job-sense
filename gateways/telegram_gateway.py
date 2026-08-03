import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message as TGMessage
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from store.messages_store import MessagesStore
from store.message_entity import MessageEntity

from common.utils import read_file, truncate

from dotenv import load_dotenv
load_dotenv()


class TelegramGateway:

    def __init__(self, telegram_token: str, messages_store: MessagesStore):
        self.bot = Bot(token=telegram_token)
        self.dispatcher = Dispatcher()

        self.dispatcher.message.register(
            self.receive_message_from_user
        )

        self.messages_store = messages_store

        self.logger = logging.getLogger("telegram_gateway")


    async def run(self):
        async with asyncio.TaskGroup() as task_group:

            task_group.create_task(
                self.dispatcher.start_polling(self.bot)
            )

            task_group.create_task(
                self.messages_store.listen(
                    gateway="telegram",
                    direction="outgoing",
                    listener=self.send_message_to_user
                )
            )


    async def _send_text(self, chat_id: str, text: str, parse_mode=None):
        return await self.bot.send_message(
            chat_id=chat_id,
            text=truncate(text, max_length=4096),
            parse_mode=parse_mode
        )


    async def send_message_to_user(self, message: MessageEntity):

        text_content = message.text_content
        file_content = message.file_content

        if text_content is None and file_content is None:
            return

        text = (text_content or "") + "\n" + (file_content or "")

        tg_message: TGMessage | None = None

        try:
            tg_message = await self._send_text(
                chat_id=message.external_chat_id,
                parse_mode="HTML",
                text=text
            )

        except TelegramAPIError as e:
            self.logger.error(truncate(e.message, max_length=200, flat=True))

            if "parse" in e.message:
                try:
                    tg_message = await self._send_text(
                        chat_id=message.external_chat_id,
                        text=text
                    )

                except TelegramAPIError as e:
                    self.logger.error(truncate(e.message, max_length=200, flat=True))

        finally:
            if tg_message is not None:
                await self.messages_store.sync_store_with_gateway(
                    message_id=message.id,
                    external_chat_id=tg_message.chat.id,
                    external_user_id=tg_message.from_user.id,
                    external_user_name=tg_message.from_user.username,
                    external_message_id=tg_message.message_id
                )


    async def receive_message_from_user(self, message: TGMessage) -> None:
        chat_id = message.chat.id

        text_content = message.text or message.caption
        file_content = await self.extract_file(message)

        await self.messages_store.store(
            role="user",
            gateway="telegram",
            direction="incoming",
            text_content=text_content,
            file_content=file_content,
            external_chat_id=message.chat.id,
            external_user_id=message.from_user.id,
            external_user_name=message.from_user.username,
            external_message_id=message.message_id
        )


    async def extract_file(self, message: TGMessage):
        document = message.document

        if document is None:
            return None

        file_name = document.file_name
        mime_type = document.mime_type

        file = await self.bot.get_file(document.file_id)
        file_stream = await self.bot.download(file)

        return await read_file(
            file_stream=file_stream,
            mime_type=mime_type,
            file_name=file_name
        )


async def main() -> None:
    telegram_token = os.getenv("TELEGRAM_TOKEN")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    telegram_gateway=TelegramGateway(
        telegram_token=telegram_token,
        messages_store=messages_store
    )

    await telegram_gateway.run()


if __name__ == "__main__":
    asyncio.run(main())
