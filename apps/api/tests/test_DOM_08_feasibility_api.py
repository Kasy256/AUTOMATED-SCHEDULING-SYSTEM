import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


def test_DOM_08_feasibility_flags_obvious_impossibilities(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    lab_type = client.post(
        "/api/v1/resource-types",
        headers=admin.auth,
        json={"key": "lab", "name": "Lab", "kind": "space"},
    ).json()["id"]
    client.post(
        f"{base}/demands",
        headers=admin.auth,
        json={
            "name": "Chemistry",
            "slot_template_id": ids["slot_template_id"],
            "spec": {
                "kind": "session",
                "sessions_per_week": 1,
                "requirements": [{"role": "lab", "resource_type_id": lab_type}],
            },
        },
    )
    # The one lecturer is available 9 h on Monday only; ask for 10 x 115 min of lecturer time.
    client.post(
        f"{base}/demands",
        headers=admin.auth,
        json={
            "name": "Calculus",
            "slot_template_id": ids["slot_template_id"],
            "spec": {
                "kind": "session",
                "sessions_per_week": 10,
                "requirements": [{"role": "lecturer", "resource_type_id": ids["resource_type_id"]}],
            },
        },
    )
    response = client.get(f"{base}/feasibility", headers=admin.auth)
    assert response.status_code == 200
    body = response.json()
    assert len(body["problem_hash"]) == 64
    codes = {issue["code"] for issue in body["issues"]}
    assert {"unfillable_requirement", "insufficient_capacity"} <= codes


def test_DOM_08_clean_schedule_has_no_issues(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    response = client.get(f"/api/v1/schedules/{ids['schedule_id']}/feasibility", headers=admin.auth)
    assert response.json()["issues"] == []
