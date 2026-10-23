from typing import Literal, Self

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CARTLYF_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: PostgresDsn
    redis_url: RedisDsn
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    db_timeout_seconds: float = 5
    jwt_secret: SecretStr = Field(min_length=32)
    web_base_url: AnyHttpUrl
    public_api_base_url: AnyHttpUrl
    cookie_secure: bool = True
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    auth_rate_limit_per_minute: int = 10
    feed_rate_limit_per_minute: int = 60
    s3_endpoint: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_bucket: str
    s3_secure: bool = True
    s3_region: str | None = None
    import_max_bytes: int = 5_000_000
    import_max_rows: int = 20_000
    solve_default_time_limit_s: int = 60
    solve_max_time_limit_s: int = 600
    solve_num_workers: int = 4
    solve_max_concurrent_per_org: int = 2
    solve_heartbeat_seconds: float = 1
    solve_stale_after_seconds: int = 30
    solve_queue_timeout_seconds: int = 3600
    draft_max_changes: int = 1000
    infeasibility_time_limit_s: int = 30
    explain_max_alternatives: int = 100
    sentry_dsn: SecretStr | None = None
    release: str | None = Field(
        default=None,
        validation_alias=AliasChoices("release", "CARTLYF_RELEASE", "RENDER_GIT_COMMIT"),
    )
    email_provider: Literal["console", "resend"] = "console"
    resend_api_key: SecretStr | None = None
    resend_api_url: AnyHttpUrl = AnyHttpUrl("https://api.resend.com")
    email_from: str | None = None
    # Set by Render on every service; there the process is never local dev, whatever else is set.
    on_render: bool = Field(default=False, validation_alias="RENDER")

    @property
    def deployed(self) -> bool:
        return self.environment in ("staging", "production")

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        problems: list[str] = []
        if self.email_provider == "resend":
            problems += [f"{f} is required for resend" for f in self._missing_resend()]
        if self.on_render and not self.deployed:
            problems.append("environment must be staging or production on Render")
        if self.deployed:
            problems += [f"{f} is unsafe outside local dev" for f in self._unsafe_when_deployed()]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _missing_resend(self) -> list[str]:
        return [f for f in ("resend_api_key", "email_from") if getattr(self, f) is None]

    def _unsafe_when_deployed(self) -> list[str]:
        # The console provider logs whole emails, sign-in links included.
        checks = {
            "cookie_secure": self.cookie_secure,
            "s3_secure": self.s3_secure,
            "web_base_url": self.web_base_url.scheme == "https",
            "public_api_base_url": self.public_api_base_url.scheme == "https",
            "email_provider": self.email_provider == "resend",
            "sentry_dsn": self.sentry_dsn is not None,
        }
        return [field for field, safe in checks.items() if not safe]


def load_settings(env_file: str | None = ".env") -> Settings:
    # Required fields come from CARTLYF_* env vars or the env file, which pyright cannot see.
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
