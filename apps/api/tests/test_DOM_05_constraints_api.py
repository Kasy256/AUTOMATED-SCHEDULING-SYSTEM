from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import Account, seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


def rule(**overrides: object) -> dict[str, Any]:
    return {
        "name": "Max 2 a day",
        "template_key": "max_load",
        "template_version": 1,
        "params": {"period": "day", "max_count": 2},
        "hard": True,
    } | overrides


def setup(client: TestClient, app: FastAPI) -> tuple[Account, dict[str, str], str]:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    return admin, ids, f"/api/v1/schedules/{ids['schedule_id']}/constraints"


def test_DOM_05_valid_instance_is_stored_normalised(client: TestClient, app: FastAPI) -> None:
    admin, ids, url = setup(client, app)
    created = client.post(
        url, headers=admin.auth, json=rule(scope={"resource_type_ids": [ids["resource_type_id"]]})
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["params"] == {"period": "day", "window": None, "max_count": 2, "max_minutes": None}
    assert client.get(f"{url}/{body['id']}", headers=admin.auth).json() == body


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"template_key": "nope"}, ["body", "template_key"]),
        ({"template_version": 9}, ["body", "template_version"]),
        ({"params": {"period": "fortnight", "max_count": 2}}, ["body", "params", "period"]),
        ({"params": {"period": "day"}}, ["body", "params"]),
        ({"template_key": "balance", "params": {"measure": "count"}}, ["body", "hard"]),
        ({"hard": False}, ["body", "weight"]),
    ],
)
def test_DOM_05_invalid_instances_rejected(
    client: TestClient, app: FastAPI, overrides: dict[str, object], loc: list[str]
) -> None:
    admin, _, url = setup(client, app)
    response = client.post(url, headers=admin.auth, json=rule(**overrides))
    assert response.status_code == 422
    assert any(e["loc"][: len(loc)] == loc for e in response.json()["errors"]), response.json()


def test_scope_series_must_be_demands_of_this_schedule(client: TestClient, app: FastAPI) -> None:
    admin, ids, url = setup(client, app)
    ok = client.post(url, headers=admin.auth, json=rule(scope={"series_ids": [ids["demand_id"]]}))
    assert ok.status_code == 201
    unknown = rule(scope={"series_ids": ["00000000-0000-4000-8000-000000000999"]})
    assert client.post(url, headers=admin.auth, json=unknown).status_code == 404


def test_update_disable_and_delete(client: TestClient, app: FastAPI) -> None:
    admin, _, url = setup(client, app)
    created = client.post(url, headers=admin.auth, json=rule()).json()
    item = f"{url}/{created['id']}"
    updated = client.put(item, headers=admin.auth, json=rule(enabled=False, hard=False, weight=3))
    assert updated.status_code == 200 and updated.json()["enabled"] is False
    assert client.delete(item, headers=admin.auth).status_code == 204
    assert client.get(item, headers=admin.auth).status_code == 404


def test_template_catalogue(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    templates = client.get("/api/v1/constraint-templates", headers=admin.auth).json()
    assert len(templates) == 14
    max_load = next(t for t in templates if t["key"] == "max_load")
    assert max_load["version"] == 1 and max_load["soft_only"] is False
    assert "period" in max_load["params_schema"]["properties"]
