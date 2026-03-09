from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import Settings
from app.machines import PluginMachine
from app.routers.root import router
from app.runtime_config import RuntimeConfig

_logger = logger.bind(classname="Main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Starting plugin")

    runtime_config = RuntimeConfig.from_settings(Settings)
    app.state.runtime_config = runtime_config

    plugin_machine = PluginMachine()
    app.state.plugin_machine = plugin_machine

    await plugin_machine.start()

    yield

    await plugin_machine.shutdown()
    _logger.info("Shutting down plugin")


app = FastAPI(
    title="LPRD WebUntis Plugin",
    version=Settings.plugin_version,
    description="LPRD plugin for WebUntis timetable data",
    lifespan=lifespan,
)

app.include_router(router)
