import json

import pytest
from fastapi.testclient import TestClient

from cartlyf_api.main import create_app
from support import make_settings


def _request_lines(out: str) -> list[dict[str, object]]:
    lines = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    return [line for line in lines if line.get("event") == "http_request"]


def test_request_log_is_json_and_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app(
        make_settings("postgresql+asyncpg://u:p@localhost:1/x", "redis://localhost:1/0")
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()
        client.get("/api/v1/calendar/feed-token-value.ics?x=query-value")
        client.get("/api/v1/no-such-route", headers={"Authorization": "Bearer bearer-value"})
    out = capsys.readouterr().out
    lines = _request_lines(out)
    assert [(line["method"], line["path"]) for line in lines] == [
        ("GET", "/api/v1/calendar/[redacted].ics"),
        ("GET", "/api/v1/no-such-route"),
    ]
    assert lines[1]["status"] == 404
    assert all(isinstance(line["duration_ms"], int) for line in lines)
    assert all("client_ip" in line for line in lines)
    for secret in ("feed-token-value", "query-value", "bearer-value"):
        assert secret not in out
