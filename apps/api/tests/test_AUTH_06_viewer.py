import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import build_world, openapi_operations

pytestmark = pytest.mark.integration
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# The caller acts on their own identity here, not on organisation data.
SELF_SERVICE_PREFIX = "/api/v1/auth/"


def test_AUTH_06_viewer_cannot_mutate_anything(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    checked: list[str] = []
    for op in openapi_operations(app):
        if op.method not in MUTATING or op.path.startswith(SELF_SERVICE_PREFIX):
            continue
        url = op.path.format(**{name: world.a_ids[name] for name in op.path_params})
        response = client.request(op.method, url, headers=world.a_viewer.auth, json=op.body)
        expected = 404 if op.path.startswith("/api/v1/platform/") else 403
        assert response.status_code == expected, f"{op.method} {op.path} -> {response.status_code}"
        checked.append(f"{op.method} {op.path}")
    assert len(checked) >= 3, checked


def test_AUTH_06_member_cannot_read_member_directory(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    assert client.get("/api/v1/members", headers=world.a_member.auth).status_code == 403
    assert client.get("/api/v1/members", headers=world.a_viewer.auth).status_code == 403
