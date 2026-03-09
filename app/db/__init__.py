from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base

_logger = logger.bind(classname="Database")

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine(database_url: str):
    global _engine
    if _engine is None:
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_async_engine(database_url, connect_args=connect_args)
        _logger.debug(f"Created async engine for {database_url.split('://')[0]}")
    return _engine


def _get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = _get_engine(database_url)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def init_db(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        # sqlite+aiosqlite:///data/plugin.db → data/plugin.db
        db_path = Path(database_url.split("///", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = _get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _logger.info("Database tables initialized")


async def get_session(database_url: str) -> AsyncGenerator[AsyncSession]:
    factory = _get_session_factory(database_url)
    async with factory() as session:
        yield session
