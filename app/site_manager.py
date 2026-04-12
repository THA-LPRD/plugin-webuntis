from __future__ import annotations

from collections.abc import Iterable
from typing import Final
from urllib.parse import urlencode

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select

from app.auth import request_with_bearer
from app.db import get_session
from app.db.models import InstalledSiteRecord

_SITE_PAGE_LIMIT: Final[int] = 100


class InstalledSite(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str


class SiteManager:
    def __init__(self, *, core_url: str, database_url: str) -> None:
        self._logger = logger.bind(classname="SiteManager")
        self._core_url = core_url.rstrip("/")
        self._database_url = database_url
        self._cache: tuple[InstalledSite, ...] | None = None

    async def get(self, *, sync: bool = False, allow_stale: bool = True) -> tuple[InstalledSite, ...]:
        if sync:
            try:
                return await self._sync_from_core()
            except Exception as exc:
                if not allow_stale:
                    raise
                cached = await self._load_cached()
                if cached:
                    self._logger.warning(
                        f"Failed to sync installed sites from core, using {len(cached)} cached site(s): {exc}"
                    )
                else:
                    self._logger.warning(f"Failed to sync installed sites from core and no cached sites exist: {exc}")
                return cached

        return await self._load_cached()

    def clear_cache(self) -> None:
        self._cache = None

    async def _load_cached(self) -> tuple[InstalledSite, ...]:
        if self._cache is not None:
            return self._cache

        async for session in get_session(self._database_url):
            result = await session.execute(select(InstalledSiteRecord).order_by(InstalledSiteRecord.slug.asc()))
            records = result.scalars().all()
            cached = tuple(InstalledSite(id=record.site_id, slug=record.slug, name=record.name) for record in records)
            self._cache = cached
            return cached

        raise RuntimeError("No database session available")

    async def _store(self, sites: Iterable[InstalledSite]) -> tuple[InstalledSite, ...]:
        normalized = tuple(sites)

        async for session in get_session(self._database_url):
            await session.execute(delete(InstalledSiteRecord))
            session.add_all(InstalledSiteRecord(site_id=site.id, slug=site.slug, name=site.name) for site in normalized)
            await session.commit()
            self._cache = normalized
            return normalized

        raise RuntimeError("No database session available")

    async def _sync_from_core(self) -> tuple[InstalledSite, ...]:
        items: list[InstalledSite] = []
        cursor: str | None = None

        async with httpx.AsyncClient() as client:
            while True:
                query = urlencode(
                    {
                        "limit": str(_SITE_PAGE_LIMIT),
                        **({"cursor": cursor} if cursor else {}),
                    }
                )
                response = await request_with_bearer(
                    client,
                    "GET",
                    f"{self._core_url}/api/v2/plugin/sites?{query}",
                    timeout=10.0,
                )
                response.raise_for_status()

                payload = response.json()
                page_items = payload.get("items")
                if not isinstance(page_items, list):
                    raise RuntimeError("Invalid plugin sites response: items must be a list")

                items.extend(InstalledSite.model_validate(item) for item in page_items)

                next_cursor = payload.get("next_cursor")
                if next_cursor is None:
                    break
                if not isinstance(next_cursor, str) or not next_cursor:
                    raise RuntimeError("Invalid plugin sites response: next_cursor must be null or string")
                cursor = next_cursor

        sites = await self._store(items)
        self._logger.info(f"Stored {len(sites)} installed site(s)")
        return sites
