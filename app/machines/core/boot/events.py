from app.statemachine import Event

MAX_RETRIES = 3


class BootStart(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class BootstrapMetadata(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class VerifyToken(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class BootstrapFailed(Event):
    pass


class FetchInstalledSites(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class CreateTemplate(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class AuthFailed(Event):
    pass


class TemplateFailed(Event):
    pass
