import pytest
from pydantic import ValidationError

from cartlyf_api.settings import load_settings


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
    settings = load_settings(env_file=None)
    assert settings.database_url.hosts()[0]["host"] == "db"
    assert settings.log_level == "INFO"
    assert settings.access_token_minutes == 15
    assert settings.cookie_secure is True


def test_settings_reject_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTLYF_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/cartlyf")
    monkeypatch.setenv("CARTLYF_REDIS_URL", "redis://cache:6379/0")
    monkeypatch.setenv("CARTLYF_JWT_SECRET", "s" * 31)
    monkeypatch.setenv("CARTLYF_WEB_BASE_URL", "http://web.test")
    with pytest.raises(ValidationError, match="jwt_secret"):
        load_settings(env_file=None)
