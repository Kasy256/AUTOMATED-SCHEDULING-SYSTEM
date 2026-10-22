import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import signup_and_confirm, solve_now

pytestmark = pytest.mark.integration


def test_HC_02_understaffed_solve_succeeds_with_gaps(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    created = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={
            "template_key": "healthcare",
            "name": "Thin ward",
            "timezone": "Africa/Kampala",
            "start_date": "2027-01-04",
            "end_date": "2027-01-05",
        },
    ).json()
    schedule_id = created["schedule"]["id"]
    nurse_type = created["resource_type_ids"]["nurse"]
    base = f"/api/v1/schedules/{schedule_id}"
    nurse = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={
            "resource_type_id": nurse_type,
            "code": "RN-1",
            "name": "Nurse 1",
            "tags": ["RN"],
            "attributes": {"contract_minutes_per_week": 2400},
        },
    )
    assert nurse.status_code == 201, nurse.text
    demand = client.post(
        f"{base}/demands",
        headers=admin.auth,
        json={
            "name": "Ward night",
            "slot_template_id": created["slot_template_ids"]["Shifts"],
            "spec": {
                "kind": "coverage",
                "slot_labels": ["Night"],
                "requirements": [
                    {
                        "role": "rn",
                        "resource_type_id": nurse_type,
                        "count_min": 2,
                        "count_max": 2,
                        "hard": False,
                        "weight": 1000,
                        "tags": ["RN"],
                    }
                ],
            },
        },
    )
    assert demand.status_code == 201, demand.text

    _, version_id = solve_now(client, admin, schedule_id)

    report = client.get(f"/api/v1/solution-versions/{version_id}/report", headers=admin.auth)
    assert report.status_code == 200, report.text
    gaps = report.json()["coverage_gaps"]
    assert len(gaps) == 2
    assert all(g["role"] == "rn" and g["required_min"] == 2 and g["assigned"] == 1 for g in gaps)
    assert len({g["starts_at"] for g in gaps}) == 2
