from datetime import date
from typing import Annotated

import httpx
from loguru import logger

from app import Settings
from app.auth import request_with_bearer
from app.machines.core.events import ErrorCleared, Tick
from app.machines.core.operate.events import (
    FetchFailed,
    FetchRequest,
    PushFailed,
    PushPayload,
)
from app.runtime_services import get_site_manager
from app.site_manager import SiteManager
from app.statemachine import Depends, Region
from app.untis import (
    UntisClient,
    build_room_payload,
    compute_next_wake_seconds,
    compute_slot_ttl,
)

_logger = logger.bind(classname="Operate")

_next_wake: dict[str, int] = {}


def pop_next_wake(room_name: str) -> int:
    return _next_wake.pop(room_name, 3600)


running = Region("running", initial="IDLE")
running_error = Region("running_error", initial="OK")

SiteManagerDep = Annotated[SiteManager, Depends(get_site_manager)]

running.defer(Tick, in_state="FETCHING")
running.defer(Tick, in_state="PUSHING")


@running.on(Tick, source="IDLE", target="FETCHING")
async def on_tick(event: Tick) -> FetchRequest:
    return FetchRequest(room_name=event.room_name)


@running.on(FetchRequest, source="FETCHING", target="PUSHING")
async def fetch(event: FetchRequest) -> PushPayload:
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

    _logger.info(
        f"Fetched '{room_name}' slot={payload.get('currentLessonId')} ttl={ttl}s next_wake={wake}s"
    )

    return PushPayload(room_name=room_name, data=payload, ttl_seconds=ttl)


@running.on(PushPayload, source="PUSHING", target="IDLE")
async def push(event: PushPayload, site_manager: SiteManagerDep) -> None:
    sites = await site_manager.get()
    if not sites:
        _logger.warning("Skipping push because no installed sites were loaded at startup")
        return

    url = f"{Settings.core_url}/api/v2/plugin/webhook/data"

    async with httpx.AsyncClient() as client:
        for site in sites:
            response = await request_with_bearer(
                client,
                "POST",
                url,
                json={
                    "site_id": site.id,
                    "topic": "timetable",
                    "entry": event.room_name,
                    "data": event.data,
                    "ttl_seconds": event.ttl_seconds,
                },
                timeout=10.0,
            )
            response.raise_for_status()

    _logger.info(
        f"Pushed '{event.room_name}' to {len(sites)} site(s) ttl={event.ttl_seconds}s"
    )


running_error.route(FetchFailed, source="OK", target="FETCH_FAILED")
running_error.route(PushFailed, source="OK", target="PUSH_FAILED")
running_error.route(ErrorCleared, source="FETCH_FAILED", target="OK")
running_error.route(ErrorCleared, source="PUSH_FAILED", target="OK")
