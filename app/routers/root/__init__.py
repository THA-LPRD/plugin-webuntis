from fastapi import APIRouter

from app.routers.root.config import router as config_router
from app.routers.root.health import router as health_router

router = APIRouter()

router.include_router(health_router)
router.include_router(config_router)

__all__ = ["router"]
