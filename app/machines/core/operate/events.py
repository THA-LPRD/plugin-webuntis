from typing import Any

from app.statemachine import Event


class FetchRequest(Event):
    def __init__(self, room_name: str) -> None:
        self.room_name = room_name


class PushPayload(Event):
    def __init__(self, room_name: str, data: dict[str, Any], token: str, ttl_seconds: int) -> None:
        self.room_name = room_name
        self.data = data
        self.token = token
        self.ttl_seconds = ttl_seconds


class FetchFailed(Event):
    pass


class PushFailed(Event):
    pass
