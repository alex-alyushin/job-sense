import os
import re
import json
import html
import logging
import asyncio

from store.message_entity import MessageEntity
from store.document_entity import DocumentEntity

from store.messages_store import MessagesStore, AsyncCursor

from utils.log import configure_logging


class ReportService:

    def __init__(self, messages_store: MessagesStore):
        self.logger = logging.getLogger("report_service")
        self.messages_store = messages_store


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="report",
            listener=self.report
        )


    ##################
    # STORE LISTENER #
    ##################

    async def report(self, cursor: AsyncCursor, message: MessageEntity):

        search_initiator = int(message.text_content)

        documents = await self.messages_store.load_search_results(
            cursor,
            search_initiator=search_initiator,
        )

        for document in documents:
            await self.messages_store.store(
                role="report",
                gateway=message.gateway,
                direction="outgoing",
                text_content=self._parse_caption(document.document),
                file_content=json.dumps(document.document, indent=2),
                file_name=self._parse_filename(document.document),
                external_chat_id=message.external_chat_id
            )


    def _parse_filename(self, document: dict) -> str:
        title = document.get("job_title")
        title_sanitized = re.sub(r'[\\/:*?"<>|]', "_", title).strip()

        return f"{title_sanitized}.txt"


    def _parse_caption(self, document: dict) -> str:
        url     = html.escape(document.get("url") or "", quote=True)
        title   = html.escape(document.get("job_title") or "")
        summary = html.escape(document.get("job_summary") or "")
        company = html.escape(document.get("company_name") or "")

        return f'<b><a href="{url}">{title}</a></b>\n<b>{company}</b>\n\n{summary}'



async def main() -> None:

    from dotenv import load_dotenv
    load_dotenv()

    configure_logging(service_name="ReportService")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    report_service = ReportService(
        messages_store=messages_store
    )

    await report_service.run()


if __name__ == "__main__":
    asyncio.run(main())
