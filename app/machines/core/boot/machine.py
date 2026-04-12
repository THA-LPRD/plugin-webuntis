import json
from typing import Annotated

import httpx
from loguru import logger

from app import Settings
from app.auth import request_with_bearer
from app.machines.core.boot.events import (
    AuthFailed,
    BootstrapFailed,
    BootstrapMetadata,
    BootStart,
    CreateTemplate,
    FetchInstalledSites,
    TemplateFailed,
    VerifyToken,
)
from app.machines.core.events import ErrorCleared
from app.runtime_config import RuntimeConfig
from app.runtime_services import get_site_manager
from app.site_manager import SiteManager
from app.statemachine import Depends, Region

_logger = logger.bind(classname="Boot")
SiteManagerDep = Annotated[SiteManager, Depends(get_site_manager)]

boot = Region("boot", initial="LOAD_CONFIG")
boot_error = Region("boot_error", initial="OK")


@boot.on(BootStart, source="LOAD_CONFIG", target="BOOTSTRAP")
async def load_config(event: BootStart) -> BootstrapMetadata:
    get_site_manager().clear_cache()
    return BootstrapMetadata(retries_remaining=event.retries_remaining)


@boot.on(BootstrapMetadata, source="BOOTSTRAP", target="VERIFY_AUTH")
async def bootstrap_metadata(event: BootstrapMetadata) -> VerifyToken:
    bootstrap_url = f"{Settings.core_url}/api/v2/plugin/bootstrap"
    _logger.info(f"Bootstrapping plugin metadata at {bootstrap_url}")

    async with httpx.AsyncClient() as client:
        response = await request_with_bearer(
            client,
            "POST",
            bootstrap_url,
            json={
                "baseUrl": Settings.plugin_base_url,
                "version": Settings.plugin_version,
                "description": Settings.plugin_description,
                "healthCheckIntervalMs": Settings.health_check_interval_ms,
                "topics": [
                    {
                        "key": "timetable",
                        "label": "Timetable",
                        "description": "Room timetable data from WebUntis",
                    },
                ],
                "configSchema": RuntimeConfig.model_json_schema(),
            },
            timeout=10.0,
        )
        response.raise_for_status()

    _logger.info("Plugin metadata bootstrapped")
    return VerifyToken(retries_remaining=event.retries_remaining)


@boot.on(VerifyToken, source="VERIFY_AUTH", target="CREATE_TEMPLATE")
async def verify_auth(event: VerifyToken) -> CreateTemplate:
    verify_url = f"{Settings.core_url}/api/v2/plugin/verify"

    async with httpx.AsyncClient() as client:
        response = await request_with_bearer(
            client,
            "GET",
            verify_url,
            timeout=10.0,
        )
        response.raise_for_status()

    _logger.info("Token verified successfully")
    return CreateTemplate(retries_remaining=event.retries_remaining)


@boot.on(CreateTemplate, source="CREATE_TEMPLATE", target="FETCH_SITES")
async def create_template(event: CreateTemplate) -> FetchInstalledSites:
    tpl_dir = Settings.template_dir_abs

    if not tpl_dir.exists():
        _logger.warning(f"Template directory {tpl_dir} not found, skipping")
        return FetchInstalledSites(retries_remaining=event.retries_remaining)

    url = f"{Settings.core_url}/api/v2/plugin/webhook/createTemplate"
    count = 0

    async with httpx.AsyncClient() as client:
        for entry in sorted(tpl_dir.iterdir()):
            if not entry.is_dir():
                continue

            html_path = entry / "template.html"
            if not html_path.exists():
                continue

            meta_path = entry / "metadata.json"
            if not meta_path.exists():
                _logger.warning(f"No metadata.json in {entry.name}, skipping")
                continue

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            template_html = html_path.read_text(encoding="utf-8")

            sample_data = None
            sample_path = entry / "sample_data.json"
            if sample_path.exists():
                sample_data = json.loads(sample_path.read_text(encoding="utf-8"))

            response = await request_with_bearer(
                client,
                "POST",
                url,
                json={
                    "name": meta["name"],
                    "description": meta.get("description"),
                    "template_html": template_html,
                    "sample_data": sample_data,
                    "variants": meta["variants"],
                    "preferred_variant_index": meta["preferred_variant_index"],
                    "version": meta.get("version"),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            count += 1
            _logger.info(f"Template '{meta['name']}' created/updated")

    _logger.info(f"Pushed {count} template(s)")
    return FetchInstalledSites(retries_remaining=event.retries_remaining)


@boot.on(FetchInstalledSites, source="FETCH_SITES", target="READY")
async def fetch_installed_sites(event: FetchInstalledSites, site_manager: SiteManagerDep) -> None:
    sites = await site_manager.get(sync=True, allow_stale=True)
    if sites:
        _logger.info(f"Loaded {len(sites)} installed site(s) at startup")
    else:
        _logger.warning("No installed sites available after startup refresh")


boot_error.route(BootstrapFailed, source="OK", target="BOOTSTRAP_FAILED")
boot_error.route(AuthFailed, source="OK", target="AUTH_FAILED")
boot_error.route(TemplateFailed, source="OK", target="TEMPLATE_FAILED")
boot_error.route(ErrorCleared, source="BOOTSTRAP_FAILED", target="OK")
boot_error.route(ErrorCleared, source="AUTH_FAILED", target="OK")
boot_error.route(ErrorCleared, source="TEMPLATE_FAILED", target="OK")
