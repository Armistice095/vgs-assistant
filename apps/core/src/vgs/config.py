"""Typed configuration read from the environment.

Every value comes from environment variables (see ``.env.example``). In deployed
environments the application refuses to start when a rule below is broken: a
misconfigured production must fail loudly, not run half-configured.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


_DEPLOYED = {Environment.STAGING, Environment.PRODUCTION}
_MIN_SECRET_CHARS = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    vgs_env: Environment = Environment.DEVELOPMENT
    vgs_log_level: str = "INFO"

    database_url: str | None = None
    test_database_url: str | None = None

    channel_adapter: str = "console"
    channel_account_id: str = ""
    channel_hmac_secret: SecretStr | None = None
    channel_hmac_max_skew_seconds: int = Field(default=300, gt=0)
    reply_window_hours: int = Field(default=24, gt=0)
    batch_window_ms: int = Field(default=3000, ge=0)

    # Draft catalogue entries are never usable by the assistant, except in
    # development and tests where this flag lets us exercise the full flow.
    allow_draft_catalog: bool = False

    master_key_id: str = "v1"
    master_key_b64: SecretStr | None = None
    master_keys_retired_json: SecretStr | None = None

    @property
    def is_deployed(self) -> bool:
        return self.vgs_env in _DEPLOYED

    @model_validator(mode="after")
    def _check_environment_rules(self) -> Self:
        problems: list[str] = []
        if self.is_deployed:
            if self.allow_draft_catalog:
                problems.append("ALLOW_DRAFT_CATALOG must be false in staging and production")
            if not self.database_url:
                problems.append("DATABASE_URL is required")
            if not self.master_key_b64:
                problems.append("MASTER_KEY_B64 is required")
            secret = self.channel_hmac_secret
            if secret is None or len(secret.get_secret_value()) < _MIN_SECRET_CHARS:
                problems.append(
                    f"CHANNEL_HMAC_SECRET is required ({_MIN_SECRET_CHARS}+ characters)"
                )
        if self.vgs_env is Environment.PRODUCTION and self.channel_adapter == "whatsapp_baileys":
            problems.append("CHANNEL_ADAPTER=whatsapp_baileys is forbidden in production")
        if problems:
            raise ValueError("; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
