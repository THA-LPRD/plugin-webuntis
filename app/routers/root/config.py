from fastapi import APIRouter, Request
from loguru import logger
from pydantic import BaseModel, Field

from app import Settings
from app.runtime_config import RuntimeConfig
from app.scheduler import reschedule_all

router = APIRouter()
_logger = logger.bind(classname="ConfigRouter")


class ConfigUpdate(BaseModel):
    sync_interval_minutes: int = Field(..., gt=0, description="Sync interval in minutes")


@router.get("/config/schema")
async def config_schema(request: Request) -> dict:
    runtime_config: RuntimeConfig = request.app.state.runtime_config
    schema = RuntimeConfig.model_json_schema()
    for field_name, field_props in schema.get("properties", {}).items():
        if getattr(field_props, "default", None) is None:
            field_props["default"] = getattr(runtime_config, field_name)
    return {"schema": schema}


@router.post("/config")
async def update_config(body: ConfigUpdate, request: Request) -> dict[str, str]:
    runtime_config: RuntimeConfig = request.app.state.runtime_config
    runtime_config.sync_interval_minutes = body.sync_interval_minutes

    plugin_machine = request.app.state.plugin_machine
    if plugin_machine.scheduler:
        reschedule_all(
            plugin_machine.scheduler,
            Settings.untis_rooms_list(),
            body.sync_interval_minutes,
        )
        _logger.info(f"Rescheduled all rooms to every {body.sync_interval_minutes} minutes")

    return {"status": "ok"}
