import asyncio
import time
from typing import Any

import httpx
from loguru import logger

from app import Settings

_logger = logger.bind(classname="Auth")
_REFRESH_WINDOW_SECONDS = 30
_token_lock = asyncio.Lock()
_cached_token: str | None = None
_cached_token_expires_at = 0.0


async def get_access_token(force_refresh: bool = False) -> str:
    global _cached_token, _cached_token_expires_at

    now = time.monotonic()
    if not force_refresh and _cached_token is not None and now < _cached_token_expires_at - _REFRESH_WINDOW_SECONDS:
        return _cached_token

    async with _token_lock:
        now = time.monotonic()
        if not force_refresh and _cached_token is not None and now < _cached_token_expires_at - _REFRESH_WINDOW_SECONDS:
            return _cached_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{Settings.workos_authkit_domain.rstrip('/')}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": Settings.client_id,
                    "client_secret": Settings.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            response.raise_for_status()

        payload = response.json()
        cached_token = str(payload["access_token"])
        _cached_token = cached_token
        _cached_token_expires_at = time.monotonic() + max(
            int(payload.get("expires_in", 300)),
            60,
        )
        _logger.debug("Minted WorkOS M2M access token")
        return cached_token


async def request_with_bearer(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"Bearer {await get_access_token()}"

    response = await client.request(method, url, headers=headers, **kwargs)
    if response.status_code != 401:
        return response

    headers["Authorization"] = f"Bearer {await get_access_token(force_refresh=True)}"
    return await client.request(method, url, headers=headers, **kwargs)
