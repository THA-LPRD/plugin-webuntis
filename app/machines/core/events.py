from app.statemachine import Event


class ErrorCleared(Event):
    pass


class Tick(Event):
    pass


class Shutdown(Event):
    pass
