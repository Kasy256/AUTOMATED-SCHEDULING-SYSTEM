import json
import logging

import pytest
import sentry_sdk
import structlog
from sentry_sdk.types import Event

from cartlyf_api.log_config import configure_logging
from cartlyf_api.sentry import init_sentry, scrub_event
from support import make_settings


def test_logs_are_json_lines(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info("hello", answer=42)
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["event"] == "hello"
    assert line["answer"] == 42
    assert line["level"] == "info"


def test_exception_logs_never_include_local_variables(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")

    def login(password: str) -> None:
        raise ValueError("boom")

    try:
        login("hunter2-secret")
    except ValueError:
        structlog.get_logger().error("failed", exc_info=True)
    out = capsys.readouterr().out
    assert "ValueError" in out
    assert "hunter2-secret" not in out


def test_access_logs_redact_calendar_feed_tokens() -> None:
    configure_logging("INFO")
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", "/api/v1/calendar/s3cr3t-T0ken_x.ics?a=1", "1.1", 200),
        None,
    )
    assert logging.getLogger("uvicorn.access").filter(record)
    message = record.getMessage()
    assert "s3cr3t-T0ken_x" not in message
    assert "/api/v1/calendar/[redacted].ics?a=1" in message


def test_sentry_events_redact_calendar_feed_tokens() -> None:
    event: Event = {"request": {"url": "https://api.test/api/v1/calendar/s3cr3t.ics"}}
    scrubbed = scrub_event(event, {})
    assert (
        scrubbed.get("request", {}).get("url") == "https://api.test/api/v1/calendar/[redacted].ics"
    )


def test_sentry_never_captures_local_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    options: dict[str, object] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: options.update(kwargs))
    init_sentry(
        make_settings(
            "postgresql+asyncpg://u:p@h/db",
            "redis://h:1/0",
            sentry_dsn="https://k@o0.ingest.sentry.io/0",
        )
    )
    assert options["dsn"] == "https://k@o0.ingest.sentry.io/0"
    assert options["include_local_variables"] is False
