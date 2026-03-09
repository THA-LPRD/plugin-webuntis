from loguru import logger
from pydantic import BaseModel, ConfigDict

from app.machines.core.boot import boot, boot_error
from app.machines.core.boot.events import (
    AuthFailed,
    BootStart,
    RegistrationFailed,
    StorageFailed,
)
from app.machines.core.events import ErrorCleared, Shutdown
from app.machines.core.operate import running, running_error
from app.machines.core.operate.events import FetchFailed, PushFailed
from app.statemachine import Event, Region, SubregionComplete, SubregionError

_logger = logger.bind(classname="Core")

core = Region("core", initial="BOOT")

core.submachine("BOOT", regions=[boot, boot_error])
core.submachine("RUNNING", regions=[running, running_error])

_BOOT_ERROR_MAP: dict[str, type[Event]] = {
    "REGISTER": RegistrationFailed,
    "STORE_CREDENTIALS": StorageFailed,
    "VERIFY_AUTH": AuthFailed,
}


async def _boot_ready(event: Event) -> bool:
    return isinstance(event, SubregionComplete) and event.terminal_state == "READY"


core.route(SubregionComplete, source="BOOT", target="RUNNING", guard=_boot_ready)
core.route(Shutdown, source="RUNNING", target="EXIT")


@core.on(SubregionError, source="BOOT")
async def handle_boot_error(
    event: SubregionError,
) -> tuple[str, BootStart] | None:
    _logger.error(f"Boot failed in {event.state_name}: {event.cause}")

    retries = getattr(event.trigger, "retries_remaining", 0)

    if retries > 0:
        _logger.warning(f"Retrying boot ({retries - 1} retries remaining)")
        return "BOOT", BootStart(retries_remaining=retries - 1)

    error_cls = _BOOT_ERROR_MAP.get(event.state_name)
    if error_cls:
        await boot_error.process_event(error_cls())

    _logger.error("No retries remaining, giving up")
    return None


_OPERATE_ERROR_MAP: dict[str, type[Event]] = {
    "FETCHING": FetchFailed,
    "PUSHING": PushFailed,
}


@core.on(SubregionError, source="RUNNING")
async def handle_operate_error(event: SubregionError) -> str:
    _logger.error(f"Operate error in {event.state_name}: {event.cause}")

    error_cls = _OPERATE_ERROR_MAP.get(event.state_name)
    if error_cls:
        if running_error.current_state != "OK":
            await running_error.process_event(ErrorCleared())
        await running_error.process_event(error_cls())

    await running.reset()
    return "RUNNING"


class MachineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    main_state: str
    boot_state: str
    running_state: str
    boot_error: str
    running_error: str
    status: str


def snapshot() -> MachineSnapshot:
    main_state = core.current_state
    boot_state = boot.current_state
    running_state = running.current_state
    boot_err = boot_error.current_state
    running_err = running_error.current_state

    any_error = boot_err != "OK" or running_err != "OK"
    if any_error:
        status = "error"
    elif main_state == "RUNNING" and running_state in ("IDLE", "FETCHING", "PUSHING"):
        status = "healthy"
    else:
        status = "starting"

    return MachineSnapshot(
        main_state=main_state,
        boot_state=boot_state,
        running_state=running_state,
        boot_error=boot_err,
        running_error=running_err,
        status=status,
    )
