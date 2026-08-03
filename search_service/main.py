import os
import json
import httpx
import asyncio
import requests
import logging

from datetime import datetime
from urllib.parse import urlencode

from pydantic import ValidationError
from search_service.schema_brightdata_linkedin import LinkedInJobsInput

from store.messages_store import MessagesStore, AsyncCursor
from store.message_entity import MessageEntity

from utils.log import configure_logging
from utils.utils import truncate


class SearchService:

    def __init__(self, brigth_data_token, messages_store: MessagesStore):
        self.logger = logging.getLogger("search_service")
        self.brigth_data_token = brigth_data_token
        self.messages_store = messages_store


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="internal",
            listener=self.search
        )


    ##################
    # STORE LISTENER #
    ##################

    async def search(self, cursor: AsyncCursor, message: MessageEntity):

        search_initiator = message.id

        await self.messages_store.store(
            role="searcher",
            gateway=message.gateway,
            direction="outgoing",
            text_content="🔎 Searching...",
            external_chat_id=message.external_chat_id,
        )

        request = self._validate_brightdata_input(message.text_content)

        if request is None:
            # todo: notify user
            return

        response = await self._brightdata_api(
            request=request
        )

        if response is None:
            # todo: notify user
            return

        records = response.text.splitlines()

        self.logger.info("Found %s records", len(records))

        for record in records:
            document = self._parse_document(record)

            if document is not None:
                await self.messages_store.store_document(
                    cursor,
                    search_initiator=search_initiator,
                    document=document
                )

        await self.messages_store.store(
            role="searcher",
            gateway=message.gateway,
            direction="report",
            text_content=search_initiator,
            external_chat_id=message.external_chat_id,
        )


    def _validate_brightdata_input(self, text_content: str):
        try:
            return LinkedInJobsInput.model_validate_json(text_content)

        except ValidationError as validation_error:
            self.logger.error(validation_error)
            return None


    async def _brightdata_api(self, request: LinkedInJobsInput):
        try:

            BASE_URL = "https://api.brightdata.com/datasets/v3/scrape"

            QUERY_PARAMETERS = {
                "dataset_id": "gd_lpfll7v5hcqtkxl6l",
                "notify": "false",
                "include_errors": "true",
                "type": "discover_new",
                "discover_by": "keyword",
            }

            url = f"{BASE_URL}?{urlencode(QUERY_PARAMETERS)}"

            payload = {
                "input": [request.model_dump(exclude_none=True)],
                "limit_per_input": 12,
            }

            headers = {
                "Authorization": f"Bearer {self.brigth_data_token}",
                "Content-Type": "application/json",
            }

            self.logger.info(
                "POST %s Payload: %s",
                truncate(url, max_length=30, flat=True),
                payload
            )

            async with httpx.AsyncClient() as async_client:
                response = await async_client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=180
                )

            response.raise_for_status()

        except httpx.TimeoutException as timeout_error:
            self.logger.error(timeout_error)
            return None

        except httpx.ConnectError as connection_error:
            self.logger.error(connection_error)
            return None

        except httpx.HTTPError as http_error:
            self.logger.error(http_error)
            return None

        self.logger.info(
            "%s %-30s %s %s",
            response.request.method,
            response.url.path[:30],
            response.status_code,
            response.reason_phrase
        )

        return response


    def _parse_document(self, document_str: str):
        try:
            document = json.loads(document_str)

            if document.get("url") is None:
                return None

            return document

        except json.JSONDecodeError:
            return None


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
