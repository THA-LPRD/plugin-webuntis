from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.statemachine.depends import resolve_and_call
from app.statemachine.errors import MachineError
from app.statemachine.event import Event, SubregionComplete, SubregionError
from app.statemachine.row import Row
from app.statemachine.state import State


class Region:
    def __init__(
        self,
        name: str,
        *,
        initial: str,
        initial_event: type[Event] | None = None,
    ) -> None:
        self.name = name
        self.initial = initial
        self.initial_event = initial_event
        self._logger = logger.bind(classname=f"Region.{name}")

        self._states: dict[str, State] = {}
        self._rows: list[Row] = []
        self._submachines: dict[str, list[Region]] = {}
        self._current: str = initial
        self._deferred: list[Event] = []

        self._ensure_state(initial)

    def _ensure_state(self, name: str) -> None:
        if name not in self._states:
            self._states[name] = State(name=name)

    @property
    def current_state(self) -> str:
        return self._current

    @property
    def is_terminal(self) -> bool:
        return not any(row.source == self._current for row in self._rows)

    # --- Definition-time API ---

    def on(
        self,
        event_type: type[Event],
        *,
        source: str,
        target: str | None = None,
        guard: Callable[[Event], Awaitable[bool]] | None = None,
    ) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._ensure_state(source)
            if target is not None:
                self._ensure_state(target)
            self._rows.append(
                Row(
                    source=source,
                    event=event_type,
                    target=target,
                    action=func,
                    guard=guard,
                )
            )
            return func

        return decorator

    def route(
        self,
        event_type: type[Event],
        *,
        source: str,
        target: str,
        guard: Callable[[Event], Awaitable[bool]] | None = None,
    ) -> None:
        self._ensure_state(source)
        self._ensure_state(target)
        self._rows.append(Row(source=source, event=event_type, target=target, guard=guard))

    def defer(self, event_type: type[Event], *, in_state: str) -> None:
        self._ensure_state(in_state)
        old = self._states[in_state]
        self._states[in_state] = State(name=old.name, defer=old.defer | frozenset({event_type}))

    # --- Submachine wiring ---

    def submachine(self, state_name: str, regions: list[Region]) -> None:
        self._ensure_state(state_name)
        self._submachines[state_name] = regions

    # --- Runtime API ---

    async def start(self) -> None:
        self._current = self.initial
        self._logger.info(f"Started in state: {self.initial}")

        if self._current in self._submachines:
            for sub in self._submachines[self._current]:
                try:
                    await sub.start()
                except MachineError as exc:
                    error = SubregionError(exc.state_name, exc.region, exc.cause, trigger=exc.trigger)
                    if await self._process_own_rows(error):
                        return
                    raise

        if self.initial_event:
            await self.process_event(self.initial_event())

    async def process_event(self, event: Event) -> bool:
        handled = await self._propagate_to_subregions(event)
        if handled:
            return True

        return await self._process_own_rows(event)

    async def reset(self) -> None:
        self._current = self.initial
        self._deferred.clear()
        for sub_regions in self._submachines.values():
            for sub in sub_regions:
                await sub.reset()

    # --- Internal ---

    async def _propagate_to_subregions(self, event: Event) -> bool:
        sub_regions = self._submachines.get(self._current)
        if not sub_regions:
            return False

        handled = False
        for sub in sub_regions:
            try:
                if await sub.process_event(event):
                    handled = True
            except MachineError as exc:
                error = SubregionError(exc.state_name, exc.region, exc.cause, trigger=exc.trigger)
                if await self._process_own_rows(error):
                    return True
                raise

        main_sub = sub_regions[0]
        if main_sub.is_terminal:
            completion = SubregionComplete(
                region_name=main_sub.name,
                terminal_state=main_sub.current_state,
            )
            await self._process_own_rows(completion)
            return True

        return handled

    async def _process_own_rows(self, event: Event) -> bool:
        for row in self._rows:
            if row.source != self._current:
                continue
            row_event: Any = row.event
            if not isinstance(event, row_event):
                continue
            if row.guard and not await row.guard(event):
                continue

            target = row.target
            forwarded: Event | None = None

            if row.action:
                try:
                    result = await resolve_and_call(row.action, event)
                except Exception as exc:
                    raise MachineError(self._current, self.name, exc, trigger=event) from exc

                target, forwarded = self._parse_action_result(result, target)

            if target is None:
                return True

            await self._transition(target)

            if forwarded is not None:
                await self.process_event(forwarded)

            return True

        state = self._states.get(self._current)
        if state and any(isinstance(event, evt_type) for evt_type in state.defer):
            self._deferred.append(event)
            self._logger.debug(f"Deferred {type(event).__name__} in {self._current}")
            return True

        return False

    @staticmethod
    def _parse_action_result(result: Any, row_target: str | None) -> tuple[str | None, Event | None]:
        if result is None:
            return row_target, None

        if isinstance(result, str):
            return result, None

        if isinstance(result, Event):
            return row_target, result

        if isinstance(result, tuple) and len(result) == 2:
            t, e = result
            if isinstance(t, str) and isinstance(e, Event):
                return t, e

        return row_target, None

    async def _transition(self, target_name: str) -> None:
        old = self._current
        self._current = target_name
        self._logger.info(f"{old} -> {target_name}")

        if target_name in self._submachines:
            for sub in self._submachines[target_name]:
                try:
                    await sub.start()
                except MachineError as exc:
                    error = SubregionError(exc.state_name, exc.region, exc.cause, trigger=exc.trigger)
                    if await self._process_own_rows(error):
                        return
                    raise

        await self._replay_deferred()

    async def _replay_deferred(self) -> None:
        if not self._deferred:
            return
        events = list(self._deferred)
        self._deferred.clear()
        for event in events:
            self._logger.debug(f"Replaying deferred {type(event).__name__}")
            await self.process_event(event)
