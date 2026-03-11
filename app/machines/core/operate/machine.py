from datetime import date
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
from app.untis import UntisClient, build_room_payload, compute_next_wake_seconds, compute_slot_ttl

_logger = logger.bind(classname="Operate")

_next_wake: dict[str, int] = {}


def pop_next_wake(room_name: str) -> int:
    return _next_wake.pop(room_name, 3600)


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

running.defer(Tick, in_state="FETCHING")
running.defer(Tick, in_state="PUSHING")


@running.on(Tick, source="IDLE", target="FETCHING")
async def on_tick(event: Tick) -> FetchRequest:
    return FetchRequest(room_name=event.room_name)


@running.on(FetchRequest, source="FETCHING", target="PUSHING")
async def fetch(event: FetchRequest, token: AuthToken) -> PushPayload:
    room_name = event.room_name

    async with UntisClient(Settings.untis_school, Settings.untis_server) as client:
        all_rooms = await client.get_rooms()
        room_map = {r["name"]: r["id"] for r in all_rooms if r.get("name")}

        room_id = room_map.get(room_name)
        if room_id is None:
            raise RuntimeError(f"Room '{room_name}' not found in WebUntis")

        periods = await client.get_timetable_for_week(room_id, date.today())

    payload = build_room_payload(periods, room_name)
    ttl = compute_slot_ttl(payload)
    wake = compute_next_wake_seconds([payload])
    _next_wake[room_name] = wake

    _logger.info(f"Fetched '{room_name}' slot={payload.get('currentLessonId')} ttl={ttl}s next_wake={wake}s")

    return PushPayload(room_name=room_name, data=payload, token=token, ttl_seconds=ttl)


@running.on(PushPayload, source="PUSHING", target="IDLE")
async def push(event: PushPayload) -> None:
    url = f"{Settings.registry_url}/api/v2/plugin/webhook/data"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                "org_slug": "default",
                "topic": "timetable",
                "entry": event.room_name,
                "data": event.data,
                "ttl_seconds": event.ttl_seconds,
            },
            headers={"Authorization": f"Bearer {event.token}"},
            timeout=10.0,
        )
        response.raise_for_status()

    _logger.info(f"Pushed '{event.room_name}' ttl={event.ttl_seconds}s")


running_error.route(FetchFailed, source="OK", target="FETCH_FAILED")
running_error.route(PushFailed, source="OK", target="PUSH_FAILED")
running_error.route(ErrorCleared, source="FETCH_FAILED", target="OK")
running_error.route(ErrorCleared, source="PUSH_FAILED", target="OK")
