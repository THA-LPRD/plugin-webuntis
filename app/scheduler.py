from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

_logger = logger.bind(classname="Scheduler")


def _job_id(room: str) -> str:
    return f"sync_{room}"


def create_room_schedulers(
    rooms: list[str],
    interval_minutes: int,
    trigger_callback: Callable[[str], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    for room in rooms:
        scheduler.add_job(
            trigger_callback,
            args=[room],
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=_job_id(room),
            max_instances=1,
            replace_existing=True,
        )
    return scheduler


def reschedule_room_in(scheduler: AsyncIOScheduler, room: str, seconds: int) -> None:
    run_at = datetime.now(UTC) + timedelta(seconds=seconds)
    scheduler.reschedule_job(_job_id(room), trigger=DateTrigger(run_date=run_at))
    _logger.debug(f"'{room}' next sync in {seconds}s ({run_at.strftime('%H:%M:%S')})")


def reschedule_all(
    scheduler: AsyncIOScheduler, rooms: list[str], interval_minutes: int
) -> None:
    for room in rooms:
        scheduler.reschedule_job(
            _job_id(room),
            trigger=IntervalTrigger(minutes=interval_minutes),
        )
