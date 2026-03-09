from pydantic import BaseModel, ConfigDict

from app.statemachine.event import Event


class State(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    defer: frozenset[type[Event]] = frozenset()

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self.name == other.name
        return NotImplemented
