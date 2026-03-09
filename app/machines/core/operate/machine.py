from typing import Annotated

import httpx
from loguru import logger
from sqlalchemy import select

from app import Settings
from app.db import get_session
from app.db.models import Credentials
from app.machines.core.events import ErrorCleared, Tick
from app.machines.core.operate.events import (
    FetchFailed,
    FetchRequest,
    PushFailed,
    PushPayload,
)
from app.statemachine import Depends, Region

_logger = logger.bind(classname="Operate")


async def _get_auth_token() -> str:
    async for session in get_session(Settings.database_url):
        result = await session.execute(
            select(Credentials).order_by(Credentials.created_at.desc()).limit(1)
        )
        return result.scalar_one().token
    raise RuntimeError("No database session available")


AuthToken = Annotated[str, Depends(_get_auth_token)]

running = Region("running", initial="IDLE")
running_error = Region("running_error", initial="OK")


@running.on(Tick, source="IDLE", target="FETCHING")
async def on_tick(event: Tick) -> FetchRequest:
    return FetchRequest(org="default")


@running.on(FetchRequest, source="FETCHING", target="PUSHING")
async def fetch(event: FetchRequest, token: AuthToken) -> PushPayload:
    data = {"mock": "data"}
    return PushPayload(
        data=data,
        token=token,
        ttl_seconds=Settings.sync_interval_minutes * 60 * 2,
    )


@running.on(PushPayload, source="PUSHING", target="IDLE")
async def push(event: PushPayload) -> None:
    url = f"{Settings.registry_url}/api/v2/plugin/webhook/data"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                "org_slug": "default",
                "topic": "timetable",
                "entry": "current",
                "data": event.data,
                "ttl_seconds": event.ttl_seconds,
            },
            headers={"Authorization": f"Bearer {event.token}"},
            timeout=10.0,
        )
        response.raise_for_status()

    _logger.info("Pushed data to timetable/current")


running_error.route(FetchFailed, source="OK", target="FETCH_FAILED")
running_error.route(PushFailed, source="OK", target="PUSH_FAILED")
running_error.route(ErrorCleared, source="FETCH_FAILED", target="OK")
running_error.route(ErrorCleared, source="PUSH_FAILED", target="OK")
