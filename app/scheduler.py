from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

JOB_ID = "sync_job"


def create_scheduler(
    interval_minutes: int,
    trigger_callback: Callable[[], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        trigger_callback,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=JOB_ID,
        max_instances=1,
        replace_existing=True,
    )
    return scheduler


def reschedule(scheduler: AsyncIOScheduler, interval_minutes: int) -> None:
    scheduler.reschedule_job(
        JOB_ID,
        trigger=IntervalTrigger(minutes=interval_minutes),
    )
