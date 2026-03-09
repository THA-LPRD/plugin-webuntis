from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.statemachine.event import Event


class InvalidTransition(Exception):
    def __init__(self, from_state: str, to_state: str, region: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.region = region
        super().__init__(f"[{region}] Invalid transition: {from_state} -> {to_state}")


class MachineError(Exception):
    def __init__(
        self,
        state_name: str,
        region: str,
        cause: Exception,
        trigger: Event | None = None,
    ) -> None:
        self.state_name = state_name
        self.region = region
        self.cause = cause
        self.trigger = trigger
        super().__init__(f"[{region}] Error in state {state_name}: {cause}")
