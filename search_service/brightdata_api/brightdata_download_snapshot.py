import httpx
import logging

from store.entities.user_entity import UserEntity

logger = logging.getLogger("brightdata_api")

async def brightdata_download_snapshot(
    brigth_data_token: str,
    snapshot_id: str,
    user: UserEntity,
    notify_user,
):
    """
    Download results from a completed Bright Data Web Scraper API async job by snapshot ID.
    Pull-based delivery with a 5 GB per-request size limit.
    Documentation: https://docs.brightdata.com/api-reference/scrapers/delivery-apis/download-snapshot
    """

    response = None

    try:
        DOWNLOAD_SNAPSHOT_URL = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

        headers = {"Authorization": f"Bearer {brigth_data_token}"}
        params = {"format": "jsonl"}

        async with httpx.AsyncClient() as async_client:
            response = await async_client.get(
                DOWNLOAD_SNAPSHOT_URL,
                headers=headers,
                params=params,
            )

            response.raise_for_status()

    except httpx.TimeoutException as timeout_error:
        logger.error(timeout_error)

    except httpx.ConnectError as connection_error:
        logger.error(connection_error)

    except httpx.HTTPError as http_error:
        logger.error(http_error)

    if response is not None:
        logger.info(
            "%s %-30s %s %s",
            response.request.method,
            response.url.path[:30],
            response.status_code,
            response.reason_phrase
        )

    return response
