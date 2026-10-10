import json

import pytest
import structlog

from cartlyf_api.log_config import configure_logging


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
