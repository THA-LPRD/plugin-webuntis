from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.statemachine.event import Event


class Row(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    source: str
    event: type[Event]
    target: str | None = None
    action: Callable[..., Awaitable[Any]] | None = None
    guard: Callable[[Event], Awaitable[bool]] | None = None
