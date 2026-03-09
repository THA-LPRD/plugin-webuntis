from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app import Settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status (healthy, starting, or error)")
    version: str = Field(..., description="Plugin version")
    main_state: str = Field(..., description="Top-level state (BOOT, RUNNING, EXIT)")
    boot_state: str = Field(..., description="Current boot submachine state")
    running_state: str = Field(..., description="Current running submachine state")
    boot_error: str = Field(..., description="Boot error region state")
    running_error: str = Field(..., description="Running error region state")
    timestamp: datetime = Field(..., description="Response timestamp")


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    plugin_machine = request.app.state.plugin_machine
    snap = plugin_machine.snapshot()
    return HealthResponse(
        status=snap.status,
        version=Settings.plugin_version,
        main_state=snap.main_state,
        boot_state=snap.boot_state,
        running_state=snap.running_state,
        boot_error=snap.boot_error,
        running_error=snap.running_error,
        timestamp=datetime.now(UTC),
    )
