import httpx
import asyncio
import logging
import contextlib

from itertools import cycle
from urllib.parse import urlencode

from store.entities.user_entity import UserEntity

from search_service.brightdata_api_schema.linkedin_jobs_input import LinkedInJobsInput
from search_service.brightdata_api.brightdata_monitor_progress import brightdata_monitor_progress, BrightDataProgress
from search_service.brightdata_api.brightdata_download_snapshot import brightdata_download_snapshot

logger = logging.getLogger("brightdata_api")


dummy_notifications = [
    "⏳ Still waiting for the API...",
    "🔄 API is still processing…",
    "🕐 Almost there, waiting for the API...",
    "⏱️ Still waiting for a response...",
    "🤞 The API should respond soon...",
    "🔧 API is working on it...",
    "💤 Still waiting for the API...",
    "🚀 Response should be coming soon...",
    "👀 Waiting for the API response...",
    "🛠️ API is still working...",
]


async def send_dummy_progress(notify_user):

    try:
        for text in cycle(dummy_notifications):
            await asyncio.sleep(15)
            await notify_user(text)

    except asyncio.CancelledError:
        raise


async def brightdata_discover_linkedin_jobs(
    brigth_data_token: str,
    request: LinkedInJobsInput,
    user: UserEntity,
    notify_user,
):
    """
    Use the Bright Data Web Scraper API to discover LinkedIn Jobs by Keyword.
    Calls the POST /datasets/v3/trigger endpoint, which returns a snapshot
    id right away; the results are then polled for and downloaded.
    Documentation: https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-discover-by-keyword
    """

    response = None
    progress_notification_task = asyncio.create_task(send_dummy_progress(notify_user))

    try:
        DISCOVER_URL = "https://api.brightdata.com/datasets/v3/trigger"

        DISCOVER_LINKEDIN_PARAMS = {
            "dataset_id": "gd_lpfll7v5hcqtkxl6l",
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "keyword",
        }

        discover_url = f"{DISCOVER_URL}?{urlencode(DISCOVER_LINKEDIN_PARAMS)}"

        payload = {
            "input": [request.model_dump(exclude_none=True)],
            "limit_per_input": 12,
        }

        headers = {
            "Authorization": f"Bearer {brigth_data_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as async_client:
            trigger_response = await async_client.post(
                discover_url,
                json=payload,
                headers=headers,
                timeout=180,
            )

            trigger_response.raise_for_status()

            progress_notification_task.cancel()

            snapshot_id = trigger_response.json()["snapshot_id"]

            logger.info(
                "%s %s %s %s snapshot: %s",
                trigger_response.request.method,
                trigger_response.url.path,
                trigger_response.status_code,
                trigger_response.reason_phrase,
                snapshot_id,
            )

            snapshot_status = await brightdata_monitor_progress(
                brigth_data_token=brigth_data_token,
                snapshot_id=snapshot_id,
                user=user,
                notify_user=notify_user,
            )

            if snapshot_status == BrightDataProgress.READY:
                response = await brightdata_download_snapshot(
                    brigth_data_token=brigth_data_token,
                    snapshot_id=snapshot_id,
                    user=user,
                    notify_user=notify_user,
                )

    except httpx.TimeoutException as timeout_error:
        logger.error(timeout_error)

    except httpx.ConnectError as connection_error:
        logger.error(connection_error)

    except httpx.HTTPError as http_error:
        logger.error(http_error)

    except (KeyError, ValueError) as response_error:
        logger.error("Unexpected trigger response: %s", response_error)

    finally:
        progress_notification_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_notification_task

    if response is not None:
        logger.info(
            "%s %s %s %s",
            response.request.method,
            response.url.path,
            response.status_code,
            response.reason_phrase
        )

    return response
