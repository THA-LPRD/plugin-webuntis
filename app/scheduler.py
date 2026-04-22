from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
    scheduler = AsyncIOScheduler(
        timezone=UTC,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": None,
        },
    )
    scheduler.add_listener(_log_job_event, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
    for room in rooms:
        scheduler.add_job(
            trigger_callback,
            args=[room],
            trigger=IntervalTrigger(minutes=interval_minutes, timezone=UTC),
            id=_job_id(room),
            replace_existing=True,
        )
    return scheduler


def reschedule_room_in(scheduler: AsyncIOScheduler, room: str, seconds: int) -> None:
    run_at = datetime.now(UTC) + timedelta(seconds=seconds)
    job = scheduler.reschedule_job(
        _job_id(room),
        trigger=IntervalTrigger(seconds=seconds, start_date=run_at, timezone=UTC),
    )
    next_run_at = getattr(job, "next_run_time", run_at)
    _logger.info(f"'{room}' next sync in {seconds}s at {next_run_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")


def reschedule_all(scheduler: AsyncIOScheduler, rooms: list[str], interval_minutes: int) -> None:
    for room in rooms:
        scheduler.reschedule_job(
            _job_id(room),
            trigger=IntervalTrigger(minutes=interval_minutes, timezone=UTC),
        )


def _log_job_event(event: JobExecutionEvent) -> None:
    if event.code == EVENT_JOB_MISSED:
        _logger.warning(
            f"Missed scheduler job '{event.job_id}' scheduled for "
            f"{event.scheduled_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        return

    if event.exception is not None:
        _logger.error(f"Scheduler job '{event.job_id}' failed: {event.exception}")
