from __future__ import annotations


class Event:
    pass


class SubregionComplete(Event):
    def __init__(self, region_name: str, terminal_state: str) -> None:
        self.region_name = region_name
        self.terminal_state = terminal_state


class SubregionError(Event):
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
