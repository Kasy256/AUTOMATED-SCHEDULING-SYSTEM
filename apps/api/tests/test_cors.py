from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from cartlyf_api.main import create_app
from support import make_settings

WEB = "https://app.example.test"


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = make_settings(
        "postgresql+asyncpg://u:p@localhost:1/x", "redis://localhost:1/0", web_base_url=WEB + "/"
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    return dict(response.headers) | {"status": str(response.status_code)}


def test_preflight_from_web_origin_allows_credentials(client: TestClient) -> None:
    headers = _preflight(client, WEB)
    assert headers["status"] == "200"
    assert headers["access-control-allow-origin"] == WEB
    assert headers["access-control-allow-credentials"] == "true"


def test_other_origins_get_no_cors_headers(client: TestClient) -> None:
    assert "access-control-allow-origin" not in _preflight(client, "https://evil.example")
    response = client.get("/api/v1/no-such-route", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_exposed_headers(client: TestClient) -> None:
    response = client.get("/api/v1/no-such-route", headers={"Origin": WEB})
    assert response.headers["access-control-allow-origin"] == WEB
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed
    assert "content-disposition" in exposed
