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


def second_demand(client: TestClient, admin: Account, ids: dict[str, str]) -> str:
    body = {
        "name": "Second",
        "slot_template_id": ids["slot_template_id"],
        "spec": {"kind": "session", "sessions_per_week": 1, "requirements": [{"role": "any"}]},
    }
    url = f"/api/v1/schedules/{ids['schedule_id']}/demands"
    response = client.post(url, headers=admin.auth, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


UNKNOWN = "00000000-0000-4000-8000-000000000999"


def test_ids_inside_params_must_be_this_orgs(client: TestClient, app: FastAPI) -> None:
    admin, ids, url = setup(client, app)
    other = second_demand(client, admin, ids)
    pairs = [{"before": ids["demand_id"], "after": other}]
    precedence = rule(template_key="precedence", params={"pairs": pairs})
    assert client.post(url, headers=admin.auth, json=precedence).status_code == 201
    unknown_series = rule(
        template_key="precedence",
        params={"pairs": [{"before": ids["demand_id"], "after": UNKNOWN}]},
    )
    assert client.post(url, headers=admin.auth, json=unknown_series).status_code == 404
    not_a_uuid = rule(
        template_key="same_time", params={"link_groups": [[ids["demand_id"], "garbage"]]}
    )
    assert client.post(url, headers=admin.auth, json=not_a_uuid).status_code == 404
    explicit = {
        "source": "explicit",
        "pairs": [{"resource_id": UNKNOWN, "series_id": ids["demand_id"], "mode": "avoid"}],
    }
    unknown_resource = rule(template_key="preference", params=explicit, hard=False, weight=1)
    assert client.post(url, headers=admin.auth, json=unknown_resource).status_code == 404


def test_rules_block_deleting_what_they_reference(client: TestClient, app: FastAPI) -> None:
    admin, ids, url = setup(client, app)
    other = second_demand(client, admin, ids)
    resource = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": ids["resource_type_id"], "code": "LEC-FREE", "name": "Free"},
    ).json()["id"]
    lab = client.post(
        "/api/v1/resource-types",
        headers=admin.auth,
        json={"key": "lab", "name": "Lab", "kind": "space"},
    ).json()["id"]
    scoped = rule(scope={"resource_ids": [resource], "resource_type_ids": [lab]})
    assert client.post(url, headers=admin.auth, json=scoped).status_code == 201
    linked = rule(template_key="same_time", params={"link_groups": [[ids["demand_id"], other]]})
    assert client.post(url, headers=admin.auth, json=linked).status_code == 201
    assert client.delete(f"/api/v1/resources/{resource}", headers=admin.auth).status_code == 409
    assert client.delete(f"/api/v1/resource-types/{lab}", headers=admin.auth).status_code == 409
    demand_url = f"/api/v1/schedules/{ids['schedule_id']}/demands/{other}"
    response = client.delete(demand_url, headers=admin.auth)
    assert response.status_code == 409
    assert "Max 2 a day" in response.json()["detail"]


def test_template_catalogue_has_display_text(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    templates = client.get("/api/v1/constraint-templates", headers=admin.auth).json()
    max_load = next(t for t in templates if t["key"] == "max_load")
    assert max_load["title"] == "Maximum workload"
    assert max_load["description"].endswith(".")
    assert max_load["params_schema"]["properties"]["max_minutes"]["x-unit"] == "minutes"


def test_constraint_responses_carry_a_summary(client: TestClient, app: FastAPI) -> None:
    admin, _, url = setup(client, app)
    created = client.post(url, headers=admin.auth, json=rule()).json()
    assert created["summary"] == "At most 2 activities per day"
    listed = {c["id"]: c["summary"] for c in client.get(url, headers=admin.auth).json()}
    assert listed[created["id"]] == "At most 2 activities per day"
