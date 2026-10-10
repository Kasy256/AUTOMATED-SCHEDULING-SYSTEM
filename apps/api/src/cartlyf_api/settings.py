from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CARTLYF_", env_file=".env", extra="ignore")

    database_url: PostgresDsn
    redis_url: RedisDsn
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    db_timeout_seconds: float = 5
    jwt_secret: SecretStr = Field(min_length=32)
    web_base_url: AnyHttpUrl
    cookie_secure: bool = True
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    auth_rate_limit_per_minute: int = 10
    s3_endpoint: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_bucket: str
    s3_secure: bool = True
    s3_region: str | None = None
    import_max_bytes: int = 5_000_000
    import_max_rows: int = 20_000


def load_settings(env_file: str | None = ".env") -> Settings:
    # Required fields come from CARTLYF_* env vars or the env file, which pyright cannot see.
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
