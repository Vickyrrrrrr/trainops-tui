from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAINOPS_", env_file=".env", extra="ignore")

    env: str = "local"
    api_token: str = "dev-token-change-me"
    database_url: str = "sqlite:///./trainops-dev.db"
    redis_url: str = "redis://localhost:6379/0"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "trainops"
    secret_key: str = Field(default="trainops-local-insecure-key-change-me")
    hf_token: str | None = None
    skypilot_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

