import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import fetch, seed_config, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def test_pin_round_trip_and_validation(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    url = f"/api/v1/schedules/{ids['schedule_id']}/pins/{ids['activity_id']}"
    ok = client.put(
        url,
        headers=admin.auth,
        json={
            "start_at": "2027-01-12T09:00:00+03:00",
            "resources": {"lecturer": [ids["resource_id"]]},
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["start_at"] == "2027-01-12T06:00:00Z"
    replaced = client.put(url, headers=admin.auth, json={"start_at": "2027-01-11T09:00:00+03:00"})
    assert replaced.json()["resources"] == {}
    pins = client.get(f"/api/v1/schedules/{ids['schedule_id']}/pins", headers=admin.auth).json()
    assert [p["activity_id"] for p in pins] == [ids["activity_id"]]
    for body, loc in [
        ({"start_at": "2027-01-13T09:00:00+03:00"}, ["body", "start_at"]),
        ({"resources": {"room": [ids["resource_id"]]}}, ["body", "resources", "room"]),
        ({}, ["body"]),
    ]:
        response = client.put(url, headers=admin.auth, json=body)
        assert response.status_code == 422, body
        assert response.json()["errors"][0]["loc"][: len(loc)] == loc
    assert client.delete(url, headers=admin.auth).status_code == 204
    assert client.delete(url, headers=admin.auth).status_code == 404


def test_regenerating_a_demand_removes_its_pins_and_audits_it(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    activity = next(
        a
        for a in client.get(f"{base}/activities", headers=admin.auth).json()
        if a["demand_id"] == ids["demand_id"]
    )
    pinned = client.put(
        f"{base}/pins/{activity['id']}",
        headers=admin.auth,
        json={"start_at": activity["candidate_starts"][0]},
    )
    assert pinned.status_code == 200
    demand = client.get(f"{base}/demands/{ids['demand_id']}", headers=admin.auth).json()
    body = {k: demand[k] for k in ("name", "slot_template_id", "spec")}
    assert (
        client.put(f"{base}/demands/{ids['demand_id']}", headers=admin.auth, json=body).status_code
        == 200
    )
    assert client.get(f"{base}/pins", headers=admin.auth).json() == []
    details = fetch(
        superuser_url(migrated_pg),
        f"SELECT details FROM audit_log WHERE target_id = '{ids['demand_id']}' "
        "AND action = 'demand.updated'",
    )
    assert details[0][0]["pins_removed"] == 1


def test_editing_a_pinned_manual_activity_must_keep_the_pin_valid(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    client.put(
        f"{base}/pins/{ids['activity_id']}",
        headers=admin.auth,
        json={"start_at": "2027-01-12T09:00:00+03:00"},
    )
    body = {
        "name": "Seed meeting",
        "duration_minutes": 60,
        "candidate_starts": ["2027-01-11T09:00:00+03:00"],
    }
    response = client.put(f"{base}/activities/{ids['activity_id']}", headers=admin.auth, json=body)
    assert response.status_code == 409
