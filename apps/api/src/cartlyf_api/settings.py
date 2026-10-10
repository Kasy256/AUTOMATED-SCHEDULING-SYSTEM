from typing import Literal

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CARTLYF_", env_file=".env", extra="ignore")

    database_url: PostgresDsn
    redis_url: RedisDsn
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    db_timeout_seconds: float = 5


def load_settings(env_file: str | None = ".env") -> Settings:
    # Required fields come from CARTLYF_* env vars or the env file, which pyright cannot see.
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
