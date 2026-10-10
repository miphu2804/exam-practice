"""Single entrypoint for environment configuration.

Every setting is read here, once, from the process environment; there is no
``.env`` file, so a fresh clone runs on the defaults (``./dev.sh``). Hosted mode
is switched on by ``BLOB_READ_WRITE_TOKEN`` (set in the Vercel project): when it
is set, exams live in Vercel Blob and visitors supply their own cookie; when it
is absent the app runs locally and writes to ``exams/``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogSettings(BaseModel):
    level: str = "INFO"


class AppConfig(BaseSettings):
    blob_read_write_token: str | None = None  # env BLOB_READ_WRITE_TOKEN; set => hosted mode
    log: LogSettings = Field(default_factory=LogSettings)  # env LOG__LEVEL
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    @property
    def hosted(self) -> bool:
        return bool(self.blob_read_write_token)


app_config = AppConfig()
