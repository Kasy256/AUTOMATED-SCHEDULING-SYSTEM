from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import Account, fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration

ROOM_SCHEMA: dict[str, Any] = {
    "version": 1,
    "attributes": [
        {"key": "room_type", "type": "enum", "enum_values": ["lecture", "lab"], "required": True},
        {"key": "floor", "type": "integer"},
    ],
}


# Any: response JSON.
def make_type(client: TestClient, admin: Account, **overrides: object) -> dict[str, Any]:
    body = {"key": "room", "name": "Room", "kind": "space", "attribute_schema": ROOM_SCHEMA}
    response = client.post("/api/v1/resource-types", headers=admin.auth, json=body | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def make_resource(
    client: TestClient, admin: Account, type_id: str, **overrides: object
) -> dict[str, Any]:
    body = {
        "resource_type_id": type_id,
        "code": "LT1",
        "name": "Lecture Theatre 1",
        "capacity": 120,
        "attributes": {"room_type": "lecture"},
    }
    response = client.post("/api/v1/resources", headers=admin.auth, json=body | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def test_DOM_01_valid_resource_round_trips(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    room = make_resource(client, admin, make_type(client, admin)["id"], tags=["b", "a", "a"])
    assert room["tags"] == ["a", "b"]
    fetched = client.get(f"/api/v1/resources/{room['id']}", headers=admin.auth)
    assert fetched.json() == room


def test_DOM_01_invalid_attribute_rejected_with_field_error(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    type_id = make_type(client, admin)["id"]
    response = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={
            "resource_type_id": type_id,
            "code": "X",
            "name": "X",
            "attributes": {"room_type": "kitchen", "floor": "two"},
        },
    )
    assert response.status_code == 422
    errors = {tuple(e["loc"]): e["msg"] for e in response.json()["errors"]}
    assert errors[("body", "attributes", "room_type")] == "must be one of: lecture, lab"
    assert errors[("body", "attributes", "floor")] == "must be a whole number"
    assert "kitchen" not in response.text and "two" not in response.text
    assert client.get("/api/v1/resources", headers=admin.auth).json() == []


def test_DOM_01_capacity_only_for_spaces(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    person = make_type(client, admin, key="lecturer", kind="person", attribute_schema={})
    response = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": person["id"], "code": "L1", "name": "L", "capacity": 3},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["body", "capacity"]


def test_DOM_01_patch_revalidates_and_clears(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    room = make_resource(client, admin, make_type(client, admin)["id"])
    url = f"/api/v1/resources/{room['id']}"
    bad = client.patch(url, headers=admin.auth, json={"attributes": {"floor": 1}})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["loc"] == ["body", "attributes", "room_type"]
    cleared = client.patch(url, headers=admin.auth, json={"capacity": None, "name": "LT 1"})
    assert cleared.status_code == 200
    assert cleared.json()["capacity"] is None and cleared.json()["name"] == "LT 1"
    assert client.patch(url, headers=admin.auth, json={"name": None}).status_code == 422


def test_DOM_01_schema_change_must_fit_existing_resources(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    rtype = make_type(client, admin)
    make_resource(client, admin, rtype["id"])
    stricter = {
        "version": 1,
        "attributes": [
            *ROOM_SCHEMA["attributes"],
            {"key": "wing", "type": "string", "required": True},
        ],
    }
    url = f"/api/v1/resource-types/{rtype['id']}"
    response = client.patch(url, headers=admin.auth, json={"attribute_schema": stricter})
    assert response.status_code == 409
    assert "LT1" in response.json()["detail"]


def test_codes_and_keys_are_unique(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    rtype = make_type(client, admin)
    duplicate_type = client.post(
        "/api/v1/resource-types",
        headers=admin.auth,
        json={"key": "room", "name": "R", "kind": "space"},
    )
    assert duplicate_type.status_code == 409
    make_resource(client, admin, rtype["id"])
    again = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={
            "resource_type_id": rtype["id"],
            "code": "LT1",
            "name": "Other",
            "attributes": {"room_type": "lab"},
        },
    )
    assert again.status_code == 409


def test_type_in_use_cannot_be_deleted(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    rtype = make_type(client, admin)
    room = make_resource(client, admin, rtype["id"])
    type_url = f"/api/v1/resource-types/{rtype['id']}"
    assert client.delete(type_url, headers=admin.auth).status_code == 409
    assert client.delete(f"/api/v1/resources/{room['id']}", headers=admin.auth).status_code == 204
    assert client.get(f"/api/v1/resources/{room['id']}", headers=admin.auth).status_code == 404
    assert client.delete(type_url, headers=admin.auth).status_code == 204
    actions = fetch(
        superuser_url(migrated_pg),
        "SELECT action FROM audit_log WHERE organisation_id = "
        f"'{admin.organisation_id}' AND target_type IN ('resource', 'resource_type') ORDER BY id",
    )
    assert [a[0] for a in actions] == [
        "resource_type.created",
        "resource.created",
        "resource.deleted",
        "resource_type.deleted",
    ]
