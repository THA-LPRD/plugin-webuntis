from pydantic import BaseModel, Field

from app.settings import _Settings


class RuntimeConfig(BaseModel):
    sync_interval_minutes: int = Field(
        default=60,
        gt=0,
        description="How often to sync data (in minutes)",
    )

    @classmethod
    def from_settings(cls, settings: _Settings) -> "RuntimeConfig":
        return cls(sync_interval_minutes=settings.sync_interval_minutes)
