from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.main import create_app
from cartlyf_api.settings import Settings

PROBLEM = "application/problem+json"


def _app() -> FastAPI:
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://u:p@localhost:1/x",
            "redis_url": "redis://localhost:1/0",
        }
    )
    app = create_app(settings)

    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    async def needs_int(n: int) -> int:
        return n

    app.add_api_route("/boom", boom)
    app.add_api_route("/needs-int", needs_int)
    return app


def test_unhandled_error_is_problem_without_leak() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
    }
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_unknown_route_is_problem_404() -> None:
    with TestClient(_app()) as client:
        response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM
    assert response.json()["title"] == "Not Found"


def test_validation_error_does_not_echo_input() -> None:
    with TestClient(_app()) as client:
        response = client.get("/needs-int", params={"n": "hunter2"})
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    assert "hunter2" not in response.text
    assert response.json()["errors"][0]["loc"] == ["query", "n"]
