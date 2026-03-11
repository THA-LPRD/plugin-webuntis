from app.statemachine import Event


class ErrorCleared(Event):
    pass


class Tick(Event):
    def __init__(self, room_name: str) -> None:
        self.room_name = room_name


class Shutdown(Event):
    pass
