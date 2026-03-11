from app.statemachine import Event

MAX_RETRIES = 3


class BootStart(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class NeedRegistration(Event):
    def __init__(self, retries_remaining: int = MAX_RETRIES) -> None:
        self.retries_remaining = retries_remaining


class CredentialsObtained(Event):
    def __init__(
        self, plugin_id: str, token: str, retries_remaining: int = MAX_RETRIES
    ) -> None:
        self.plugin_id = plugin_id
        self.token = token
        self.retries_remaining = retries_remaining


class VerifyToken(Event):
    def __init__(self, token: str, retries_remaining: int = MAX_RETRIES) -> None:
        self.token = token
        self.retries_remaining = retries_remaining


class RegistrationFailed(Event):
    pass


class StorageFailed(Event):
    pass


class CreateTemplate(Event):
    def __init__(self, token: str, retries_remaining: int = MAX_RETRIES) -> None:
        self.token = token
        self.retries_remaining = retries_remaining


class AuthFailed(Event):
    pass


class TemplateFailed(Event):
    pass
