import os
import json
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message as TGMessage, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.filters import Command

from store.messages_store import MessagesStore, AsyncCursor
from store.message_entity import MessageEntity

from utils.utils import read_file, truncate
from utils.log import configure_logging


class TelegramGateway:

    def __init__(self, telegram_token: str, messages_store: MessagesStore):
        self.logger = logging.getLogger("telegram_gateway")
        self.bot = Bot(token=telegram_token)
        self.dispatcher = Dispatcher()
        self.messages_store = messages_store

        self.dispatcher.message.register(
            self.resolve_session,
            Command("restart")
        )

        self.dispatcher.message.register(
            self.receive_message
        )


    async def run(self):
        async with asyncio.TaskGroup() as task_group:

            task_group.create_task(
                self.dispatcher.start_polling(self.bot)
            )

            task_group.create_task(
                self.messages_store.listen(
                    gateway="telegram",
                    direction="outgoing",
                    listener=self.send_message
                )
            )


    async def receive_message(self, message: TGMessage) -> None:
        chat_id = message.chat.id

        text_content = message.text or message.caption
        file_content = await self._extract_file(message)

        await self.messages_store.store(
            role="user",
            gateway="telegram",
            direction="incoming",
            text_content=text_content,
            file_content=file_content,
            file_name=None, # todo: store
            external_chat_id=str(message.chat.id),
            external_user_id=str(message.from_user.id),
            external_user_name=str(message.from_user.username),
            external_message_id=str(message.message_id)
        )


    async def _extract_file(self, message: TGMessage):
        document = message.document

        if document is None:
            return None

        file_name = document.file_name
        mime_type = document.mime_type

        file_object = await self.bot.get_file(document.file_id)
        file_stream = await self.bot.download(file_object)

        return await read_file(
            file_stream=file_stream,
            mime_type=mime_type,
            file_name=file_name,
        )


    ##################
    # STORE LISTENER #
    ##################

    async def send_message(self, cursor: AsyncCursor, message: MessageEntity):
        delivered_message: TGMessage | None = None

        try:
            delivered_message = await self._send_outgoing_message(
                chat_id=message.external_chat_id,
                text_content=message.text_content,
                file_content=message.file_content,
                file_name=message.file_name,
                parse_mode="HTML",
            )

        except TelegramAPIError as e:
            self.logger.error(truncate(e.message, max_length=200, flat=True))

            if "parse" in e.message:
                try:
                    delivered_message = await self._send_outgoing_message(
                        chat_id=message.external_chat_id,
                        text_content=message.text_content,
                        file_content=message.file_content,
                        file_name=message.file_name,
                    )

                except TelegramAPIError as e:
                    self.logger.error(truncate(e.message, max_length=200, flat=True))

        finally:
            if delivered_message is not None:
                await self.messages_store.sync_store_with_gateway(
                    cursor,
                    message_id=message.id,
                    external_chat_id=str(delivered_message.chat.id),
                    external_user_id=str(delivered_message.from_user.id),
                    external_user_name=str(delivered_message.from_user.username),
                    external_message_id=str(delivered_message.message_id)
                )


    async def _send_outgoing_message(
        self, chat_id: str,
        text_content=None,
        file_content=None,
        file_name=None,
        parse_mode=None
    ):

        if file_content is not None:

            caption = truncate(text_content, max_length=1024)

            document = BufferedInputFile(
                file=file_content.encode("utf-8"),
                filename=file_name
            )

            return await self.bot.send_document(
                chat_id=chat_id,
                parse_mode=parse_mode,
                document=document,
                caption=caption,
            )

        if text_content is not None:

            # @todo: send long message by chunks
            text = truncate(text_content, max_length=4096)

            return await self.bot.send_message(
                chat_id=chat_id,
                parse_mode=parse_mode,
                text=text,
            )

        return None


    # todo: debug
    async def resolve_session(self, message: TGMessage) -> None:
        await self.messages_store.resolve_session(
            external_chat_id=str(message.chat.id)
        )


async def main() -> None:

    from dotenv import load_dotenv
    load_dotenv()

    configure_logging(service_name="Telegram")

    telegram_token = os.getenv("TELEGRAM_TOKEN")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
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
