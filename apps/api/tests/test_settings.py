from pathlib import Path

import pytest
from pydantic import ValidationError

from cartlyf_api.settings import load_settings
from support import make_settings

EXAMPLE_ENV = Path(__file__).resolve().parents[3] / ".env.example"


def test_settings_require_database_and_redis_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CARTLYF_DATABASE_URL", raising=False)
    monkeypatch.delenv("CARTLYF_REDIS_URL", raising=False)
    with pytest.raises(ValidationError):
        load_settings(env_file=None)


def test_settings_read_prefixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTLYF_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/cartlyf")
    monkeypatch.setenv("CARTLYF_REDIS_URL", "redis://cache:6379/0")
    monkeypatch.setenv("CARTLYF_JWT_SECRET", "s" * 32)
    monkeypatch.setenv("CARTLYF_WEB_BASE_URL", "http://web.test")
    monkeypatch.setenv("CARTLYF_PUBLIC_API_BASE_URL", "http://api.test")
    monkeypatch.setenv("CARTLYF_S3_ENDPOINT", "account.r2.cloudflarestorage.com")
    monkeypatch.setenv("CARTLYF_S3_ACCESS_KEY", "access")
    monkeypatch.setenv("CARTLYF_S3_SECRET_KEY", "secret")
    monkeypatch.setenv("CARTLYF_S3_BUCKET", "cartlyf")
    settings = load_settings(env_file=None)
    assert settings.database_url.hosts()[0]["host"] == "db"
    assert settings.log_level == "INFO"
    assert settings.access_token_minutes == 15
    assert settings.cookie_secure is True
    assert settings.s3_secure is True
    assert settings.import_max_bytes == 5_000_000
    assert settings.feed_rate_limit_per_minute == 60


def test_settings_reject_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTLYF_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/cartlyf")
    monkeypatch.setenv("CARTLYF_REDIS_URL", "redis://cache:6379/0")
    monkeypatch.setenv("CARTLYF_JWT_SECRET", "s" * 31)
    monkeypatch.setenv("CARTLYF_WEB_BASE_URL", "http://web.test")
    with pytest.raises(ValidationError, match="jwt_secret"):
        load_settings(env_file=None)


def _deployed(**overrides: object) -> dict[str, object]:
    return {
        "environment": "staging",
        "web_base_url": "https://app-staging.example.test",
        "public_api_base_url": "https://api-staging.example.test",
        "cookie_secure": True,
        "s3_secure": True,
        "email_provider": "resend",
        "resend_api_key": "re_test",
        "email_from": "Cartlyf <no-reply@example.test>",
        "sentry_dsn": "https://key@o1.ingest.sentry.io/1",
        **overrides,
    }


def test_deployed_settings_accept_safe_values() -> None:
    settings = make_settings("postgresql+asyncpg://u:p@db/x", "redis://r/0", **_deployed())
    assert settings.deployed


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cookie_secure", False),
        ("s3_secure", False),
        ("web_base_url", "http://app.example.test"),
        ("public_api_base_url", "http://api.example.test"),
        ("email_provider", "console"),
        ("sentry_dsn", None),
    ],
)
def test_deployed_settings_reject_unsafe_values(
    environment: str, field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match=field):
        make_settings(
            "postgresql+asyncpg://u:p@db/x",
            "redis://r/0",
            **_deployed(environment=environment, **{field: value}),
        )


@pytest.mark.parametrize("missing", ["resend_api_key", "email_from"])
def test_resend_requires_key_and_sender(missing: str) -> None:
    with pytest.raises(ValidationError, match=missing):
        make_settings(
            "postgresql+asyncpg://u:p@db/x",
            "redis://r/0",
            **{
                "email_provider": "resend",
                "resend_api_key": "re_test",
                "email_from": "no-reply@example.test",
                missing: None,
            },
        )


def test_local_settings_allow_dev_values() -> None:
    settings = load_settings(env_file=str(EXAMPLE_ENV))
    assert settings.environment == "local"
    assert not settings.deployed
    assert settings.email_provider == "console"


def test_release_falls_back_to_render_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CARTLYF_RELEASE", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert load_settings(env_file=str(EXAMPLE_ENV)).release == "abc123"
    monkeypatch.setenv("CARTLYF_RELEASE", "v1")
    assert load_settings(env_file=str(EXAMPLE_ENV)).release == "v1"


def test_render_host_without_deployed_environment_refuses_to_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Render sets RENDER=true; a missing CARTLYF_ENVIRONMENT must not mean "local dev" there.
    monkeypatch.delenv("CARTLYF_ENVIRONMENT", raising=False)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValidationError, match="environment"):
        load_settings(env_file=str(EXAMPLE_ENV))
