import os
import json
import time
import asyncio
import logging

from psycopg import AsyncCursor

from pydantic import BaseModel

from store.entities.message_entity import MessageEntity
from store.entities.user_entity import UserEntity
from store.messages_store import MessagesStore

from search_service.brightdata_api_schema.linkedin_jobs_input import LinkedInJobsInput
from search_service.brightdata_api.brightdata_discover_linkedin_jobs import brightdata_discover_linkedin_jobs
from search_service.brightdata_api.validate_linkedin_jobs_input import validate_brightdata_linkedin_jobs_input

from embedding.embedder import Embedder

from utils.log import configure_logging
from utils.utils import truncate

from pathlib import Path


class SearchService:

    def __init__(self, brigth_data_token, messages_store: MessagesStore):
        self.logger = logging.getLogger("search_service")
        self.brigth_data_token = brigth_data_token
        self.messages_store = messages_store
        self.embedder = Embedder()


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="searcher",
            listener=self.search
        )


    ##################
    # STORE LISTENER #
    ##################

    async def search(self, cursor: AsyncCursor, message: MessageEntity):

        call_id = message.llm_response["call_id"]
        search_input = message.llm_response["arguments"]

        # 1. Ensure user

        user: UserEntity = await self.messages_store.ensure_user(cursor, message=message)

        if user is None:
            self.logger.error("[ERROR] User not found")
            await self._NOTIFY_REPORT(call_id=call_id, user=user)
            return

        # 2. Validate search params

        request = validate_brightdata_linkedin_jobs_input(search_input)

        if request is None:
            await self._NOTIFY_USER(text="🚧 <b>Invalid request</b>", user=user)
            await self._NOTIFY_REPORT(call_id=call_id, user=user)
            return

        # 3. BrightData API call

        await self._NOTIFY_USER(
            text=f"🔎 <b>Searching...</b>\n\n{self._format_search_params(request)}<button>хуй</button>",
            user=user,
        )

        response = await brightdata_discover_linkedin_jobs(
            brigth_data_token=self.brigth_data_token,
            request=request,
            user=user,
            notify_user=lambda text: self._NOTIFY_USER(text=text, user=user),
        )

        if response is None:
            await self._NOTIFY_USER(text="🪫 <b>No results</b>", user=user)
            await self._NOTIFY_REPORT(call_id=call_id, user=user)
            return

        # 4. Parse documents

        documents: list[dict] = []
        records: list[str] = response.text.splitlines()

        for record in records:
            document = self._parse_document(record=record)
            if document is not None:
                documents.append(document)

        self.logger.info("Found %s records", len(records))
        self.logger.info("Parsed %s documents", len(documents))

        if not documents:
            await self._NOTIFY_USER(text="🪫 <b>No results</b>", user=user)
            await self._NOTIFY_REPORT(call_id=call_id, user=user)
            return

        # 5. Calculate embeddings and store documents

        # todo: self.document_to_vector(...)

        embeddings = self.embedder.encode_batch(
            texts=[
                self._extract_relevant_fields(
                    document=document,
                    relevant_fields=[
                        "job_title",
                        "job_summary",
                        "job_description_formatted"
                    ]
                ) for document in documents
            ]
        )

        for document, embedding in zip(documents, embeddings):
            await self.messages_store.store_document(
                cursor,
                document=document,
                embedding=embedding,
                call_id=call_id,
                user_id=user.id,
            )

        # 6. Notify report service

        return await self._NOTIFY_REPORT(call_id=call_id, user=user)


    def _parse_document(self, record: str) -> dict:
        try:
            document = json.loads(record)

            if document.get("url") is None:
                return None

            return document

        except json.JSONDecodeError:
            return None


    def _extract_relevant_fields(
        self,
        document: dict,
        relevant_fields: list[str],
    ) -> str:
        values = []

        for field in relevant_fields:
            values.append(document.get(field) or "")

        return "\n\n".join(values)


    async def _NOTIFY_USER(
        self, *,
        text: str,
        user: UserEntity,
    ):
        return await self.messages_store.store(
            role="searcher",
            gateway=user.gateway,
            direction="user",
            text_content=truncate(text, max_length=1024),
            external_chat_id=user.external_chat_id,
            external_user_id=user.external_user_id,
            external_user_name=user.external_user_name,
        )


    async def _NOTIFY_REPORT(self, call_id: str, user: UserEntity):
        await self.messages_store.store(
            role="searcher",
            gateway=user.gateway,
            direction="report",
            # hack for report
            text_content=call_id,
            external_chat_id=user.external_chat_id,
            external_user_id=user.external_user_id,
            external_user_name=user.external_user_name,
        )


    def _format_search_params(self, request_model: BaseModel) -> str:
        lines = []

        for key, value in request_model.model_dump(exclude_none=True).items():
            if value in (None, "", []):
                continue

            lines.append(f"<b>{key}:</b> {json.dumps(value, ensure_ascii=False)}")

        return "\n".join(lines)


    # debug
    def _dump_to_file(self, data: str, user: UserEntity):
        timestamp = int(time.time() * 1000)
        debug_path = Path(f"tmp/brightdata_response_{user.id}_{timestamp}.json")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(data, encoding="utf-8")

        self.logger.info(
            "Bright Data response saved to %s",
            debug_path,
        )


async def main() -> None:

    from dotenv import load_dotenv
    load_dotenv()

    configure_logging(service_name="SearchService")

    brigth_data_token = os.getenv("BRIGHT_DATA_TOKEN")

    messages_store = await MessagesStore.create(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    search_service = SearchService(
        brigth_data_token=brigth_data_token,
        messages_store=messages_store
    )

    await search_service.run()


if __name__ == "__main__":
    asyncio.run(main())
