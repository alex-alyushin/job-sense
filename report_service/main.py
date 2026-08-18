import os
import re
import json
import html
import logging
import asyncio

from psycopg import AsyncCursor

from store.entities.document_entity import DocumentEntity
from store.entities.message_entity import MessageEntity
from store.messages_store import MessagesStore

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

        # hack
        call_id = message.text_content

        results: list[tuple[
            DocumentEntity, # document
            float           # cv_similarity
        ]] = await self.messages_store.load_documents(
            cursor,
            call_id=call_id,
        )

        for rank, (document, cv_similarity) in enumerate(results):
            # To User: each document
            await self.messages_store.store(
                role="report",
                gateway=message.gateway,
                direction="user",
                text_content=self._parse_caption(document.document),
                file_content=json.dumps(document.document, indent=2),
                file_name=self._parse_filename(document.document),
                external_chat_id=message.external_chat_id,
                external_user_id=message.external_user_id,
                external_user_name=message.external_user_name,
                attributes={
                    "relevance": {
                        "cv_similarity": int(cv_similarity * 100),
                        "rank": rank,
                    }
                },
            )

        report_to_user = self._make_report_to_user(results=results)
        report_to_llm = self._make_report_to_llm(results=results)

        if len(results):
            # To User only if has results
            await self.messages_store.store(
                role="report",
                gateway=message.gateway,
                direction="user",
                text_content=report_to_user,
                external_chat_id=message.external_chat_id,
                external_user_id=message.external_user_id,
                external_user_name=message.external_user_name,
                # attributes={}
            )

        # To LLM anyway
        await self.messages_store.store(
            role="assistant",
            gateway=message.gateway,
            direction="assistant",
            external_chat_id=message.external_chat_id,
            external_user_id=message.external_user_id,
            external_user_name=message.external_user_name,
            llm_response={
                "type": "function_call_output",
                "output": report_to_llm,
                "call_id": call_id,
            }
        )


    def _make_report_to_user(self, results: list[tuple[DocumentEntity, float]]):

        lines = [f"📦 <b>Found {len(results)} documents</b>\n"]

        for document, cv_similarity in results:
            url     = html.escape(document.document.get("url") or "", quote=True)
            title   = html.escape(document.document.get("job_title") or "")
            rel     = int(cv_similarity * 100)

            lines.append(f'<code>{rel}% CV match</code> <a href="{url}">{title}</a>')

        return "\n".join(lines)


    def _make_report_to_llm(self, results: list[tuple[DocumentEntity, float]]):

        lines = [f"Found {len(results)} documents:\n"]

        for document, cv_similarity in results:
            url         = html.escape(document.document.get("url") or "", quote=True)
            job_title   = html.escape(document.document.get("job_title") or "")
            job_summary = html.escape(document.document.get("job_summary") or "")

            lines.append(f"Job title: {job_title} (relevance: {cv_similarity})\nurl: {url}\nsummary: {job_summary}\n")

        return "\n".join(lines)


    def _parse_filename(self, document: dict) -> str:
        title = document.get("job_title") or ""
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
