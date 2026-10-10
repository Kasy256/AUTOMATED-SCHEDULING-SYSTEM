from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.errors import (
    Conflict,
    PayloadTooLarge,
    RateLimited,
    Unauthorized,
    Unprocessable,
    field_error,
)
from cartlyf_api.main import create_app
from support import make_settings

PROBLEM = "application/problem+json"


def _app() -> FastAPI:
    settings = make_settings("postgresql+asyncpg://u:p@localhost:1/x", "redis://localhost:1/0")
    app = create_app(settings)

    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    async def needs_int(n: int) -> int:
        return n

    async def conflict() -> None:
        raise Conflict("Already a member")

    async def unauthorized() -> None:
        raise Unauthorized()

    async def rate_limited() -> None:
        raise RateLimited(retry_after=17)

    async def unprocessable() -> None:
        raise Unprocessable(
            [field_error(("body", "attributes", "seats"), "must be a whole number")]
        )

    async def too_large() -> None:
        raise PayloadTooLarge("File is larger than 5000000 bytes")

    app.add_api_route("/unprocessable", unprocessable)
    app.add_api_route("/too-large", too_large)
    app.add_api_route("/conflict", conflict)
    app.add_api_route("/unauthorized", unauthorized)
    app.add_api_route("/rate-limited", rate_limited)
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


def test_domain_error_maps_to_problem() -> None:
    with TestClient(_app()) as client:
        response = client.get("/conflict")
    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "Already a member",
    }


def test_unauthorized_sets_www_authenticate() -> None:
    with TestClient(_app()) as client:
        response = client.get("/unauthorized")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_rate_limited_sets_retry_after() -> None:
    with TestClient(_app()) as client:
        response = client.get("/rate-limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"


def test_unprocessable_lists_field_errors() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.get("/unprocessable")
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    assert response.json()["errors"] == [
        {
            "loc": ["body", "attributes", "seats"],
            "msg": "must be a whole number",
            "type": "value_error",
        }
    ]


def test_payload_too_large() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.get("/too-large")
    assert response.status_code == 413
    assert response.json()["detail"] == "File is larger than 5000000 bytes"
