from typing import Any

from app.statemachine import Event


class FetchRequest(Event):
    def __init__(self, org: str) -> None:
        self.org = org


class PushPayload(Event):
    def __init__(self, data: Any, token: str, ttl_seconds: int) -> None:
        self.data = data
        self.token = token
        self.ttl_seconds = ttl_seconds


class FetchFailed(Event):
    pass


class PushFailed(Event):
    pass
