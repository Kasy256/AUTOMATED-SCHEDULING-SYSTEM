import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import build_world, openapi_operations, substitute_ids, url_for

pytestmark = pytest.mark.integration
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# The caller acts on their own identity here, not on organisation data.
SELF_SERVICE_PREFIX = "/api/v1/auth/"
# Configuration routes: members (scheduled people) may not read them.
CONFIG_PREFIXES = (
    "/api/v1/resource-types", "/api/v1/resources", "/api/v1/schedules",
    "/api/v1/constraint-templates", "/api/v1/imports",
)  # fmt: skip


def test_AUTH_06_viewer_cannot_mutate_anything(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    checked: list[str] = []
    for op in openapi_operations(app):
        if op.method not in MUTATING or op.path.startswith(SELF_SERVICE_PREFIX):
            continue
        url = url_for(op, world.a_ids)
        body = substitute_ids(op.body, world.a_ids)
        response = client.request(op.method, url, headers=world.a_viewer.auth, json=body)
        expected = 404 if op.path.startswith("/api/v1/platform/") else 403
        assert response.status_code == expected, f"{op.method} {op.path} -> {response.status_code}"
        checked.append(f"{op.method} {op.path}")
    assert len(checked) >= 3, checked


def test_AUTH_06_member_cannot_read_member_directory(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    assert client.get("/api/v1/members", headers=world.a_member.auth).status_code == 403
    assert client.get("/api/v1/members", headers=world.a_viewer.auth).status_code == 403


def test_AUTH_06_member_cannot_read_configuration(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    reads = [op for op in openapi_operations(app)
             if op.method == "GET" and op.path.startswith(CONFIG_PREFIXES)]  # fmt: skip
    assert reads
    for op in reads:
        response = client.get(url_for(op, world.a_ids), headers=world.a_member.auth)
        assert response.status_code == 403, f"GET {op.path} -> {response.status_code}"
