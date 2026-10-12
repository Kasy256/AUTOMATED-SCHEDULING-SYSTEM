from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import Account, seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


# Any: response JSON.
def setup(client: TestClient, app: FastAPI) -> tuple[Account, dict[str, str], str]:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    return admin, ids, f"/api/v1/schedules/{ids['schedule_id']}"


def session_demand(ids: dict[str, str], **spec: object) -> dict[str, Any]:
    return {
        "name": "Calculus",
        "slot_template_id": ids["slot_template_id"],
        "spec": {
            "kind": "session",
            "sessions_per_week": 2,
            "requirements": [{"role": "lecturer", "resource_type_id": ids["resource_type_id"]}],
        }
        | spec,
    }


def generated(
    client: TestClient, admin: Account, base: str, demand_id: str
) -> list[dict[str, Any]]:
    activities = client.get(f"{base}/activities", headers=admin.auth).json()
    return [a for a in activities if a["demand_id"] == demand_id]


def test_DOM_03_session_demand_creates_activities(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    response = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids))
    assert response.status_code == 201, response.text
    demand = response.json()
    assert demand["activity_count"] == 2
    activities = generated(client, admin, base, demand["id"])
    assert len(activities) == 2
    assert all(a["series_id"] == demand["id"] for a in activities)
    assert all(len(a["candidate_starts"]) == 10 for a in activities)  # P1, P2 x Mon-Fri
    assert activities[0]["requirements"][0]["resource_type_id"] == ids["resource_type_id"]


def test_DOM_04_coverage_demand_via_api(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    body = {
        "name": "Ward",
        "slot_template_id": ids["slot_template_id"],
        "spec": {
            "kind": "coverage",
            "requirements": [{"role": "nurse", "count_min": 2, "count_max": 3}],
        },
    }
    demand = client.post(f"{base}/demands", headers=admin.auth, json=body).json()
    activities = generated(client, admin, base, demand["id"])
    assert len(activities) == 10  # 5 days x 2 slots
    assert {a["requirements"][0]["count_max"] for a in activities} == {3}


def test_editing_a_demand_keeps_the_activities_it_still_generates(
    client: TestClient, app: FastAPI
) -> None:
    admin, ids, base = setup(client, app)
    demand = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids)).json()
    url = f"{base}/demands/{demand['id']}"
    before = {
        a["name"].rsplit(" ", 1)[-1]: a["id"] for a in generated(client, admin, base, demand["id"])
    }
    renamed = session_demand(ids) | {"name": "Calculus II"}
    assert client.put(url, headers=admin.auth, json=renamed).json()["pins_removed"] == 0
    after = generated(client, admin, base, demand["id"])
    assert {a["id"] for a in after} == set(before.values())
    assert all(a["name"].startswith("Calculus II") for a in after)
    more = client.put(url, headers=admin.auth, json=session_demand(ids, sessions_per_week=3)).json()
    assert more["activity_count"] == 3
    grown = {
        a["name"].rsplit(" ", 1)[-1]: a["id"] for a in generated(client, admin, base, demand["id"])
    }
    assert grown["#1"] == before["#1"] and grown["#2"] == before["#2"] and len(grown) == 3
    client.put(url, headers=admin.auth, json=session_demand(ids, sessions_per_week=1))
    assert [a["id"] for a in generated(client, admin, base, demand["id"])] == [before["#1"]]
    assert client.delete(url, headers=admin.auth).status_code == 204
    assert generated(client, admin, base, demand["id"]) == []


def test_schedule_date_changes_keep_the_weeks_that_still_overlap(
    client: TestClient, app: FastAPI
) -> None:
    admin, ids, base = setup(client, app)
    demand = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids)).json()
    first_week = {a["id"] for a in generated(client, admin, base, demand["id"])}
    assert (
        client.patch(base, headers=admin.auth, json={"end_date": "2027-01-22"}).status_code == 200
    )
    two_weeks = generated(client, admin, base, demand["id"])
    assert len(two_weeks) == 4 and first_week <= {a["id"] for a in two_weeks}
    second_week = {a["id"] for a in two_weeks} - first_week
    # The seed's manual activity sits in the first week; it would block the move (409).
    manual = client.delete(f"{base}/activities/{ids['activity_id']}", headers=admin.auth)
    assert manual.status_code == 204
    moved = client.patch(base, headers=admin.auth, json={"start_date": "2027-01-18"})
    assert moved.status_code == 200, moved.text
    assert {a["id"] for a in generated(client, admin, base, demand["id"])} == second_week


def test_expansion_errors_are_field_errors(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    body = session_demand(ids, slot_labels=["P9"])
    response = client.post(f"{base}/demands", headers=admin.auth, json=body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["body", "spec", "slot_labels"]


def test_schedule_and_slot_template_changes_regenerate(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    demand = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids)).json()
    longer = client.patch(base, headers=admin.auth, json={"end_date": "2027-01-22"})
    assert longer.status_code == 200
    assert len(generated(client, admin, base, demand["id"])) == 4  # 2 weeks x 2
    template_url = f"{base}/slot-templates/{ids['slot_template_id']}"
    only_p1 = {
        "name": "Periods",
        "definition": {
            "version": 1,
            "slots": [
                {
                    "label": "P1",
                    "weekdays": [0, 1, 2, 3, 4],
                    "start_minute": 510,
                    "duration_minutes": 115,
                }
            ],
        },
    }
    assert client.put(template_url, headers=admin.auth, json=only_p1).status_code == 200
    activities = generated(client, admin, base, demand["id"])
    assert all(len(a["candidate_starts"]) == 5 for a in activities)
    assert client.delete(template_url, headers=admin.auth).status_code == 409


def test_slot_template_change_that_breaks_a_demand_conflicts(
    client: TestClient, app: FastAPI
) -> None:
    admin, ids, base = setup(client, app)
    client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids, slot_labels=["P2"]))
    only_p1 = {
        "name": "Periods",
        "definition": {
            "version": 1,
            "slots": [
                {"label": "P1", "weekdays": [0], "start_minute": 510, "duration_minutes": 115}
            ],
        },
    }
    response = client.put(
        f"{base}/slot-templates/{ids['slot_template_id']}", headers=admin.auth, json=only_p1
    )
    assert response.status_code == 409
    assert "Calculus" in response.json()["detail"]


def test_manual_activities(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    manual = client.get(f"{base}/activities/{ids['activity_id']}", headers=admin.auth).json()
    assert manual["demand_id"] is None and manual["candidate_starts"][0] == "2027-01-11T06:00:00Z"
    outside = {
        "name": "X",
        "duration_minutes": 60,
        "candidate_starts": ["2027-02-01T09:00:00+03:00"],
    }
    response = client.post(f"{base}/activities", headers=admin.auth, json=outside)
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["body", "candidate_starts", 0]
    shrink = client.patch(base, headers=admin.auth, json={"start_date": "2027-01-13"})
    assert shrink.status_code == 409
    demand = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids)).json()
    one = generated(client, admin, base, demand["id"])[0]
    assert client.delete(f"{base}/activities/{one['id']}", headers=admin.auth).status_code == 409


def test_requirement_referencing_unknown_type_is_not_found(
    client: TestClient, app: FastAPI
) -> None:
    admin, ids, base = setup(client, app)
    body = session_demand(ids)
    body["spec"]["requirements"][0]["resource_type_id"] = "00000000-0000-4000-8000-000000000999"
    assert client.post(f"{base}/demands", headers=admin.auth, json=body).status_code == 404


def test_slot_template_can_be_deleted_after_its_demands(client: TestClient, app: FastAPI) -> None:
    admin, ids, base = setup(client, app)
    demand = client.post(f"{base}/demands", headers=admin.auth, json=session_demand(ids)).json()
    template = client.post(
        f"{base}/slot-templates",
        headers=admin.auth,
        json={
            "name": "Extra",
            "definition": {
                "version": 1,
                "slots": [
                    {"label": "X1", "weekdays": [0], "start_minute": 600, "duration_minutes": 60}
                ],
            },
        },
    ).json()
    body = session_demand(ids) | {"slot_template_id": template["id"]}
    put = client.put(f"{base}/demands/{demand['id']}", headers=admin.auth, json=body)
    assert put.status_code == 200
    assert client.delete(f"{base}/demands/{demand['id']}", headers=admin.auth).status_code == 204
    url = f"{base}/slot-templates/{template['id']}"
    assert client.delete(url, headers=admin.auth).status_code == 204
