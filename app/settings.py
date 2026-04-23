import tomllib
from enum import Enum
from functools import cache, cached_property
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@cache
def _get_project() -> dict:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]


def _get_version() -> str:
    return _get_project()["version"]


def _get_description() -> str:
    return _get_project()["description"]


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

    core_url: str = Field(
        default="http://localhost:3000",
        description="LPRD core base URL (no trailing slash, no /api/v2)",
        frozen=True,
    )

    workos_authkit_domain: str = Field(
        description="WorkOS AuthKit domain used to mint M2M access tokens",
        frozen=True,
    )

    client_id: str = Field(
        description="WorkOS M2M client id for this plugin application",
        min_length=1,
        frozen=True,
    )

    client_secret: str = Field(
        description="WorkOS M2M client secret for this plugin application",
        min_length=1,
        frozen=True,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///data/plugin.db",
        description="Database connection URL (SQLite or PostgreSQL)",
        frozen=True,
    )

    plugin_base_url: str = Field(
        default="http://localhost:8001",
        description="This plugin's public base URL",
        frozen=True,
    )

    timezone: str = Field(
        default="Europe/Berlin",
        description="IANA timezone used for logs, payload timestamps, and scheduler calculations",
        frozen=True,
    )

    health_check_interval_ms: int = Field(
        default=30_000,
        description="Plugin health check interval reported during bootstrap",
        ge=30_000,
        frozen=True,
    )

    sync_interval_minutes: int = Field(
        default=6,
        description="How often to sync data from the source (in minutes)",
        gt=0,
        frozen=True,
    )

    boot_max_retries: int = Field(
        default=3,
        description="Maximum number of boot retry attempts",
        ge=0,
        frozen=True,
    )

    boot_backoff_base_seconds: int = Field(
        default=2,
        description="Base delay in seconds for exponential boot retry backoff",
        gt=0,
        frozen=True,
    )

    boot_backoff_max_seconds: int = Field(
        default=60,
        description="Maximum delay in seconds for boot retry backoff",
        gt=0,
        frozen=True,
    )

    # WebUntis (anonymous auth — no credentials needed)
    untis_server: str = Field(
        description="WebUntis server base URL (e.g. https://neilo.webuntis.com)",
        frozen=True,
    )

    untis_school: str = Field(
        description="WebUntis school name (subdomain identifier)",
        frozen=True,
    )

    untis_rooms: str = Field(
        description="Comma-separated list of room names to sync (e.g. 'EDV1,B201')",
        min_length=1,
        frozen=True,
    )

    template_dir: str = Field(
        default="templates",
        description="Path to template directory (absolute or relative to cwd)",
        frozen=True,
    )

    def untis_rooms_list(self) -> list[str]:
        return [r.strip() for r in self.untis_rooms.split(",") if r.strip()]

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA name such as 'Europe/Berlin' or 'America/Chicago'") from exc
        return value

    @computed_field
    @cached_property
    def template_dir_abs(self) -> Path:
        p = Path(self.template_dir)
        return p if p.is_absolute() else p.resolve()

    @computed_field
    @cached_property
    def timezone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @computed_field
    @cached_property
    def plugin_version(self) -> str:
        return _get_version()

    @computed_field
    @cached_property
    def plugin_description(self) -> str:
        return _get_description()
