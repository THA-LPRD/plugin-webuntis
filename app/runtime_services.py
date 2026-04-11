from __future__ import annotations

from app.site_manager import SiteManager

_site_manager: SiteManager | None = None


def set_site_manager(site_manager: SiteManager) -> None:
    global _site_manager
    _site_manager = site_manager


def clear_site_manager() -> None:
    global _site_manager
    _site_manager = None


def get_site_manager() -> SiteManager:
    if _site_manager is None:
        raise RuntimeError("SiteManager has not been initialized")
    return _site_manager
