import json
from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import Settings
from app.db import get_session
from app.db.models import Credentials
from app.machines.core.boot.events import (
    AuthFailed,
    BootStart,
    CreateTemplate,
    CredentialsObtained,
    NeedRegistration,
    RegistrationFailed,
    StorageFailed,
    TemplateFailed,
    VerifyToken,
)
from app.machines.core.events import ErrorCleared
from app.statemachine import Depends, Region

_logger = logger.bind(classname="Boot")


async def _get_db_session() -> AsyncGenerator[AsyncSession]:
    async for session in get_session(Settings.database_url):
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_db_session)]

boot = Region("boot", initial="LOAD_CONFIG")
boot_error = Region("boot_error", initial="OK")


@boot.on(BootStart, source="LOAD_CONFIG")
async def load_config(
    event: BootStart, session: DbSession
) -> tuple[str, VerifyToken] | tuple[str, NeedRegistration]:
    result = await session.execute(
        select(Credentials).order_by(Credentials.created_at.desc()).limit(1)
    )
    creds = result.scalar_one_or_none()
    if creds:
        _logger.info(f"Found existing credentials (plugin_id={creds.plugin_id})")
        return "VERIFY_AUTH", VerifyToken(
            token=creds.token, retries_remaining=event.retries_remaining
        )
    return "REGISTER", NeedRegistration(retries_remaining=event.retries_remaining)


@boot.on(NeedRegistration, source="REGISTER", target="STORE_CREDENTIALS")
async def register(event: NeedRegistration) -> CredentialsObtained:
    register_url = f"{Settings.registry_url}/api/v2/plugin/register"
    _logger.info(f"Registering with registry at {register_url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            register_url,
            json={
                "registration_key": Settings.registration_key,
                "base_url": Settings.plugin_base_url,
                "version": Settings.plugin_version,
            },
            timeout=10.0,
        )
        response.raise_for_status()

    data = response.json()
    _logger.info(f"Registered successfully (plugin_id={data['plugin_id']})")
    return CredentialsObtained(
        plugin_id=data["plugin_id"],
        token=data["token"],
        retries_remaining=event.retries_remaining,
    )


@boot.on(CredentialsObtained, source="STORE_CREDENTIALS", target="VERIFY_AUTH")
async def store_credentials(
    event: CredentialsObtained, session: DbSession
) -> VerifyToken:
    session.add(Credentials(plugin_id=event.plugin_id, token=event.token))
    await session.commit()
    _logger.info("Credentials stored")
    return VerifyToken(token=event.token, retries_remaining=event.retries_remaining)


@boot.on(VerifyToken, source="VERIFY_AUTH", target="CREATE_TEMPLATE")
async def verify_auth(event: VerifyToken) -> CreateTemplate:
    verify_url = f"{Settings.registry_url}/api/v2/plugin/verify"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            verify_url,
            headers={"Authorization": f"Bearer {event.token}"},
            timeout=10.0,
        )
        response.raise_for_status()

    _logger.info("Token verified successfully")
    return CreateTemplate(token=event.token, retries_remaining=event.retries_remaining)


@boot.on(CreateTemplate, source="CREATE_TEMPLATE", target="READY")
async def create_template(event: CreateTemplate) -> None:
    tpl_dir = Settings.template_dir_abs

    if not tpl_dir.exists():
        _logger.warning(f"Template directory {tpl_dir} not found, skipping")
        return

    url = f"{Settings.registry_url}/api/v2/plugin/webhook/createTemplate"
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

            response = await client.post(
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
                headers={"Authorization": f"Bearer {event.token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            count += 1
            _logger.info(f"Template '{meta['name']}' created/updated")

    _logger.info(f"Pushed {count} template(s)")


boot_error.route(RegistrationFailed, source="OK", target="REGISTRATION_FAILED")
boot_error.route(StorageFailed, source="OK", target="STORAGE_FAILED")
boot_error.route(AuthFailed, source="OK", target="AUTH_FAILED")
boot_error.route(TemplateFailed, source="OK", target="TEMPLATE_FAILED")
boot_error.route(ErrorCleared, source="REGISTRATION_FAILED", target="OK")
boot_error.route(ErrorCleared, source="STORAGE_FAILED", target="OK")
boot_error.route(ErrorCleared, source="AUTH_FAILED", target="OK")
boot_error.route(ErrorCleared, source="TEMPLATE_FAILED", target="OK")
