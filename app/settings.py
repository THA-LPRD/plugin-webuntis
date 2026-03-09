import tomllib
from enum import Enum
from functools import cached_property
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_version() -> str:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]["version"]


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
        validate_default=True,
        extra="ignore",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level for the application",
        min_length=1,
        frozen=True,
    )

    registration_key: str = Field(
        description="Key used to register this plugin with the LPRD registry",
        min_length=1,
        frozen=True,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///data/plugin.db",
        description="Database connection URL (SQLite or PostgreSQL)",
        frozen=True,
    )

    registry_url: str = Field(
        default="http://localhost:8000",
        description="LPRD registry base URL (no trailing slash, no /api/v2)",
        frozen=True,
    )

    plugin_base_url: str = Field(
        default="http://localhost:8001",
        description="This plugin's public URL for registration",
        frozen=True,
    )

    sync_interval_minutes: int = Field(
        default=60,
        description="How often to sync data from the source (in minutes)",
        gt=0,
        frozen=True,
    )

    # WebUntis
    untis_server: str = Field(
        description="WebUntis server hostname (e.g. neilo.webuntis.com)",
        frozen=True,
    )

    untis_school: str = Field(
        description="WebUntis school name (login identifier)",
        frozen=True,
    )

    untis_username: str = Field(
        description="WebUntis API username",
        frozen=True,
    )

    untis_password: str = Field(
        description="WebUntis API password",
        frozen=True,
    )

    untis_useragent: str = Field(
        default="LPRD-WebUntis-Plugin",
        description="User-agent string sent to WebUntis",
        frozen=True,
    )

    untis_rooms: str = Field(
        description="Comma-separated list of room names to sync (e.g. 'EDV1,B201')",
        min_length=1,
        frozen=True,
    )

    def untis_rooms_list(self) -> list[str]:
        return [r.strip() for r in self.untis_rooms.split(",") if r.strip()]

    @computed_field
    @cached_property
    def plugin_version(self) -> str:
        return _get_version()
