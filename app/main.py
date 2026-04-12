from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import Settings
from app.machines import PluginMachine
from app.routers.root import router
from app.runtime_config import RuntimeConfig
from app.runtime_services import clear_site_manager, set_site_manager
from app.site_manager import SiteManager

_logger = logger.bind(classname="Main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Starting plugin")

    runtime_config = RuntimeConfig.from_settings(Settings)
    app.state.runtime_config = runtime_config

    site_manager = SiteManager(
        core_url=Settings.core_url,
        database_url=Settings.database_url,
    )
    set_site_manager(site_manager)
    app.state.site_manager = site_manager

    plugin_machine = PluginMachine(site_manager=site_manager)
    app.state.plugin_machine = plugin_machine

    await plugin_machine.start()

    yield

    await plugin_machine.shutdown()
    clear_site_manager()
    _logger.info("Shutting down plugin")


app = FastAPI(
    title="LPRD WebUntis Plugin",
    version=Settings.plugin_version,
    description="LPRD plugin for WebUntis timetable data",
    lifespan=lifespan,
)

app.include_router(router)
