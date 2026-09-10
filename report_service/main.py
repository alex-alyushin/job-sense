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

from workplace.workplace_type import WorkplaceType, normalize_workplace_type
from workplace.classify_by_rules import classify_by_rules
from workplace.classify_by_llm import (
    INSTRUCTIONS,
    SCHEMA,
    SCHEMA_NAME,
    build_classification_input,
    parse_classification_output,
)

from utils.log import configure_logging


# Postings are collected far above what anyone reads, so only the closest
# matches are reported. A user with no CV has nothing to rank against; the
# cut still applies, because a hundred postings help no one either way.
REPORTED_AT_MOST = 15


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
        """
        Two kinds of message arrive on this channel: the search service
        saying a call's documents are stored, and the LLM service answering
        the work format question this service asks below.
        """

        attributes = message.attributes or {}

        if "llm_reply" in attributes:
            return await self._report_checked(cursor, message)

        return await self._report_found(cursor, message)


    async def _report_found(self, cursor: AsyncCursor, message: MessageEntity):

        # hack
        call_id = message.text_content

        search = (message.attributes or {}).get("search") or {}
        requested = normalize_workplace_type(search.get("remote"))

        results = await self.messages_store.load_documents(cursor, call_id=call_id)

        if requested is None:
            return await self._publish(cursor, message, call_id=call_id, results=results)

        # Postings that say their work format outright are settled here; the
        # rest are worth one LLM call, asked for as a message.

        pending = [
            (document.id, document.document)
            for document, _ in results
            if classify_by_rules(document.document) is None
        ]

        if not pending:
            return await self._publish_matching(
                cursor, message,
                call_id=call_id, requested=requested, results=results, by_llm={},
            )

        return await self._ASK_LLM(
            message, call_id=call_id, requested=requested, pending=pending,
        )


    async def _report_checked(self, cursor: AsyncCursor, message: MessageEntity):

        attributes = message.attributes or {}
        context = (attributes.get("llm_reply") or {}).get("context") or {}

        call_id = context.get("call_id")
        requested = normalize_workplace_type(context.get("remote"))

        if call_id is None or requested is None:
            self.logger.error("[ERROR] Work format answer without a request context")
            return

        llm_error = attributes.get("llm_error")

        if llm_error:
            self.logger.error("[ERROR] Work format check failed: %s", llm_error)

        results = await self.messages_store.load_documents(cursor, call_id=call_id)

        await self._publish_matching(
            cursor, message,
            call_id=call_id,
            requested=requested,
            results=results,
            by_llm=parse_classification_output(attributes.get("llm_output")),
            llm_error=llm_error,
        )


    async def _publish_matching(
        self, cursor: AsyncCursor, message: MessageEntity, *,
        call_id: str,
        requested: WorkplaceType,
        results: list[tuple[DocumentEntity, float]],
        by_llm: dict[int, WorkplaceType],
        llm_error: str | None = None,
    ):
        """
        Keep only the postings whose work format is the requested one.
        A posting nobody could classify is left out rather than shown as a
        match.
        """

        matching = []
        unknown = 0

        for document, cv_similarity in results:
            workplace_type = classify_by_rules(document.document) or by_llm.get(document.id)

            if workplace_type is None:
                unknown += 1

            if workplace_type == requested:
                matching.append((document, cv_similarity))

        self.logger.info(
            "Work format %s: kept %s of %s (unclassified %s)",
            requested, len(matching), len(results), unknown,
        )

        lines = [
            f"🧭 <b>{requested} check:</b> "
            f"{len(matching)} of {len(results)} jobs match"
        ]

        if llm_error:
            lines.append("⚠️ Some postings could not be checked and were left out.")

        await self._NOTIFY_USER(message, text="\n".join(lines))

        await self._publish(cursor, message, call_id=call_id, results=matching)


    async def _publish(
        self, cursor: AsyncCursor, message: MessageEntity, *,
        call_id: str,
        results: list[tuple[DocumentEntity, float]],
    ):

        found = len(results)
        results = self._best_of(results)

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

        report_to_user = self._make_report_to_user(results=results, found=found)
        report_to_llm = self._make_report_to_llm(results=results)

        if len(results):
            # To User only if has results
            await self._NOTIFY_USER(message, text=report_to_user)

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


    def _best_of(
        self,
        results: list[tuple[DocumentEntity, float]],
    ) -> list[tuple[DocumentEntity, float]]:
        """
        Keep the closest matches, worst of them first, so the strongest job
        is the last one the user reads.
        """

        by_similarity = sorted(
            results,
            key=lambda result: result[1] or 0.0,
            reverse=True,
        )

        return sorted(
            by_similarity[:REPORTED_AT_MOST],
            key=lambda result: result[1] or 0.0,
        )


    async def _NOTIFY_USER(self, message: MessageEntity, *, text: str):
        await self.messages_store.store(
            role="report",
            gateway=message.gateway,
            direction="user",
            text_content=text,
            external_chat_id=message.external_chat_id,
            external_user_id=message.external_user_id,
            external_user_name=message.external_user_name,
        )


    async def _ASK_LLM(
        self, message: MessageEntity, *,
        call_id: str,
        requested: WorkplaceType,
        pending: list[tuple[int, dict]],
    ):
        """
        Hand the undecided postings to the LLM service. The answer comes back
        on this same channel, where `_report_checked` picks the report up
        again -- only the call id and the requested format have to travel
        with it, because the rules are re-applied on the way back.
        """

        self.logger.info(
            "Asking the LLM service for the work format of %s postings",
            len(pending),
        )

        await self.messages_store.store(
            role="report",
            gateway=message.gateway,
            direction="llm",
            external_chat_id=message.external_chat_id,
            external_user_id=message.external_user_id,
            external_user_name=message.external_user_name,
            attributes={
                "llm_request": {
                    "instructions": INSTRUCTIONS,
                    "input": build_classification_input(pending),
                    "schema": SCHEMA,
                    "schema_name": SCHEMA_NAME,
                },
                "llm_reply": {
                    "direction": "report",
                    "role": "report",
                    "context": {
                        "call_id": call_id,
                        "remote": str(requested),
                    },
                },
            },
        )


    def _make_report_to_user(
        self,
        results: list[tuple[DocumentEntity, float]],
        found: int | None = None,
    ):

        if found is not None and found > len(results):
            # Say so, rather than report the cut as the whole of the search.
            heading = f"📦 <b>Best {len(results)} of {found} documents</b>"
        else:
            heading = f"📦 <b>Found {len(results)} documents</b>"

        lines = [heading + "\n"]

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
