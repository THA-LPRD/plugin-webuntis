from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app import Settings
from app.db import init_db
from app.machines.core import MachineSnapshot, core, snapshot
from app.machines.core.boot.events import BootStart
from app.machines.core.events import Shutdown, Tick
from app.machines.core.operate.machine import pop_next_wake
from app.scheduler import create_room_schedulers, reschedule_room_in
from app.statemachine import Event


class PluginMachine:
    def __init__(self) -> None:
        self._logger = logger.bind(classname="PluginMachine")
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._scheduler: Any = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def shutdown(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._logger.info("Scheduler stopped")

        self._queue.put_nowait(Shutdown())
        if self._task:
            await self._task

    def push_event(self, event: Event) -> None:
        self._queue.put_nowait(event)

    async def push_room_tick(self, room_name: str) -> None:
        await self._queue.put(Tick(room_name=room_name))

    def snapshot(self) -> MachineSnapshot:
        return snapshot()

    @property
    def scheduler(self) -> Any:
        return self._scheduler

    async def _run(self) -> None:
        await init_db(Settings.database_url)

        await core.start()
        await core.process_event(BootStart(retries_remaining=Settings.boot_max_retries))

        if core.current_state == "RUNNING":
            self._scheduler = create_room_schedulers(
                Settings.untis_rooms_list(),
                Settings.sync_interval_minutes,
                self.push_room_tick,
            )
            self._scheduler.start()
            self._logger.info(
                f"Scheduler started for {len(Settings.untis_rooms_list())} room(s)"
            )
            await self._event_loop()

    async def _event_loop(self) -> None:
        while True:
            event = await self._queue.get()

            if isinstance(event, Shutdown):
                self._logger.info("Shutdown event received")
                break

            await core.process_event(event)

            if isinstance(event, Tick) and self._scheduler:
                next_secs = pop_next_wake(event.room_name)
                reschedule_room_in(self._scheduler, event.room_name, next_secs)
