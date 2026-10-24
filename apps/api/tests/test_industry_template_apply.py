from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import Account, add_member, fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration

URL = "/api/v1/schedules/from-template"


def body(**overrides: object) -> dict[str, Any]:
    return {
        "template_key": "education",
        "name": "Term 1",
        "timezone": "Africa/Kampala",
        "start_date": "2026-01-12",
        "end_date": "2026-01-16",
    } | overrides


def apply(client: TestClient, admin: Account, **overrides: object) -> dict[str, Any]:
    response = client.post(URL, headers=admin.auth, json=body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_apply_creates_types_schedule_slots_and_rules(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    created = apply(client, admin)
    schedule_id = created["schedule"]["id"]
    assert set(created["resource_type_ids"]) == {"lecturer", "room", "student_group"}

    types = {t["key"]: t for t in client.get("/api/v1/resource-types", headers=admin.auth).json()}
    assert types["room"]["kind"] == "space"
    roles = types["lecturer"]["attribute_schema"]["attributes"][0]["enum_values"]
    assert roles == ["Full-Time", "Part-Time", "Faculty Dean"]

    schedule = client.get(f"/api/v1/schedules/{schedule_id}", headers=admin.auth).json()
    assert [p["name"] for p in schedule["day_parts"]["parts"]] == ["morning", "afternoon"]
    slots = client.get(f"/api/v1/schedules/{schedule_id}/slot-templates", headers=admin.auth)
    [slot_template] = slots.json()
    assert len(slot_template["definition"]["slots"]) == 4
    assert created["slot_template_ids"] == {"Teaching periods": slot_template["id"]}

    rules = client.get(f"/api/v1/schedules/{schedule_id}/constraints", headers=admin.auth).json()
    assert len(rules) == 12 and all(r["enabled"] for r in rules)
    (stability,) = [r for r in rules if r["template_key"] == "stability"]
    assert (stability["hard"], stability["weight"]) == (False, 100)  # repairs work out of the box
    daily = next(r for r in rules if r["name"] == "Lecturer: at most 2 sessions a day")
    assert daily["scope"]["resource_type_ids"] == [created["resource_type_ids"]["lecturer"]]


def test_apply_is_audited(client: TestClient, app: FastAPI, migrated_pg: PostgresContainer) -> None:
    admin = signup_and_confirm(client, app)
    created = apply(client, admin)
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT target_id::text, details->>'template' FROM audit_log "
        f"WHERE organisation_id = '{admin.organisation_id}' "
        "AND action = 'schedule.created_from_template'",
    )
    assert rows == [(created["schedule"]["id"], "education@v2")]


def test_apply_twice_reuses_types(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    first = apply(client, admin)
    second = apply(client, admin, name="Term 2")
    assert first["resource_type_ids"] == second["resource_type_ids"]
    assert first["schedule"]["id"] != second["schedule"]["id"]
    assert len(client.get("/api/v1/resource-types", headers=admin.auth).json()) == 3


def test_apply_conflicting_type_kind_is_409(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    clash = {"key": "lecturer", "name": "Lecture hall", "kind": "space"}
    assert client.post("/api/v1/resource-types", headers=admin.auth, json=clash).status_code == 201
    response = client.post(URL, headers=admin.auth, json=body())
    assert response.status_code == 409
    assert "lecturer" in response.json()["detail"]
    assert client.get("/api/v1/schedules", headers=admin.auth).json() == []
    assert len(client.get("/api/v1/resource-types", headers=admin.auth).json()) == 1


def test_apply_unknown_template_is_404(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    response = client.post(URL, headers=admin.auth, json=body(template_key="retail"))
    assert response.status_code == 404


def test_viewer_cannot_apply(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    viewer = add_member(client, app, admin, ["viewer"])
    assert client.post(URL, headers=viewer.auth, json=body()).status_code == 403


def test_apply_rejects_same_kind_type_missing_template_attributes(
    client: TestClient, app: FastAPI
) -> None:
    # Without `role`, the weekly caps scoped to role=Full-Time would silently match nobody.
    admin = signup_and_confirm(client, app)
    bare = {"key": "lecturer", "name": "Lecturer", "kind": "person"}
    assert client.post("/api/v1/resource-types", headers=admin.auth, json=bare).status_code == 201
    response = client.post(URL, headers=admin.auth, json=body())
    assert response.status_code == 409
    assert "role" in response.json()["detail"]


def test_apply_reuses_a_type_with_extra_attributes(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    template = client.get("/api/v1/industry-templates", headers=admin.auth).json()[0]
    lecturer = next(t for t in template["resource_types"] if t["key"] == "lecturer")
    schema = lecturer["attribute_schema"]
    extra = {"key": "office", "type": "string", "required": False}
    richer = lecturer | {
        "attribute_schema": schema | {"attributes": [*schema["attributes"], extra]}
    }
    created = client.post("/api/v1/resource-types", headers=admin.auth, json=richer)
    assert created.status_code == 201, created.text
    assert apply(client, admin)["resource_type_ids"]["lecturer"] == created.json()["id"]


def test_conflict_on_a_later_type_rolls_back_earlier_ones(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    clash = {"key": "student_group", "name": "Groups", "kind": "person"}
    assert client.post("/api/v1/resource-types", headers=admin.auth, json=clash).status_code == 201
    assert client.post(URL, headers=admin.auth, json=body()).status_code == 409
    keys = [t["key"] for t in client.get("/api/v1/resource-types", headers=admin.auth).json()]
    assert keys == ["student_group"]
    assert client.get("/api/v1/schedules", headers=admin.auth).json() == []
    audit = fetch(
        superuser_url(migrated_pg),
        "SELECT count(*) FROM audit_log WHERE organisation_id = "
        f"'{admin.organisation_id}' AND action LIKE 'resource_type.%'",
    )
    assert audit == [(1,)]
