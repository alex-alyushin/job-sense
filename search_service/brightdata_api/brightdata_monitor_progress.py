import httpx
import asyncio
import logging

from enum import StrEnum

from store.entities.user_entity import UserEntity

logger = logging.getLogger("brightdata_api")

class BrightDataProgress(StrEnum):
    READY = "ready"
    FAILED = "failed"
    UNKNOWN = "unknown"


async def brightdata_monitor_progress(
    brigth_data_token: str,
    snapshot_id: str,
    user: UserEntity,
    notify_user,
):
    """
    Use Bright Data Web Scraper API management endpoints to monitor Progress.
    GET /datasets/v3/progress/ returns snapshot or job status as JSON.
    Documentation: https://docs.brightdata.com/api-reference/scrapers/management-apis/monitor-progress
    """

    snapshot_status = BrightDataProgress.UNKNOWN

    try:
        MONITOR_PROGRESS_URL = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"

        headers = {
            "Authorization": f"Bearer {brigth_data_token}",
        }

        async with httpx.AsyncClient() as async_client:

            while True:

                polling_response = await async_client.get(
                    MONITOR_PROGRESS_URL,
                    headers=headers,
                )

                polling_response.raise_for_status()
                result = polling_response.json()

                snapshot_status = result["status"]

                await notify_user(f"📡 Progress status: {snapshot_status}")

                logger.info(
                    "[Monitor progress] snapshot: %s, status: %s",
                    snapshot_id, snapshot_status,
                )

                if snapshot_status == BrightDataProgress.READY:
                    break

                if snapshot_status == BrightDataProgress.FAILED:
                    break

                await asyncio.sleep(30)

    except httpx.TimeoutException as timeout_error:
        logger.error(timeout_error)
        snapshot_status = BrightDataProgress.FAILED

    except httpx.ConnectError as connection_error:
        logger.error(connection_error)
        snapshot_status = BrightDataProgress.FAILED

    except httpx.HTTPError as http_error:
        logger.error(http_error)
        snapshot_status = BrightDataProgress.FAILED


    return snapshot_status
