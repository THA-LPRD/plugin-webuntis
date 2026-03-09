from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app import Settings
from app.db import init_db
from app.machines.core import MachineSnapshot, core, snapshot
from app.machines.core.boot.events import BootStart
from app.machines.core.events import Shutdown, Tick
from app.scheduler import create_scheduler
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

    async def push_tick(self) -> None:
        await self._queue.put(Tick())

    def snapshot(self) -> MachineSnapshot:
        return snapshot()

    @property
    def scheduler(self) -> Any:
        return self._scheduler

    async def _run(self) -> None:
        await init_db(Settings.database_url)

        await core.start()
        await core.process_event(BootStart())

        if core.current_state == "RUNNING":
            self._scheduler = create_scheduler(
                Settings.sync_interval_minutes, self.push_tick
            )
            self._scheduler.start()
            self._logger.info("Scheduler started")
            await self._event_loop()

    async def _event_loop(self) -> None:
        while True:
            event = await self._queue.get()

            if isinstance(event, Shutdown):
                self._logger.info("Shutdown event received")
                break

            await core.process_event(event)
