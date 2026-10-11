import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import signup_and_confirm

pytestmark = pytest.mark.integration

TERM = {
    "name": "Term 1 2027",
    "timezone": "Africa/Kampala",
    "start_date": "2027-01-11",
    "end_date": "2027-01-15",
    "day_parts": {
        "version": 1,
        "parts": [
            {"name": "morning", "start_minute": 480, "end_minute": 780},
            {"name": "afternoon", "start_minute": 780, "end_minute": 1080},
        ],
    },
}
PERIODS = {
    "name": "Teaching periods",
    "definition": {
        "version": 1,
        "slots": [
            {
                "label": "P1",
                "weekdays": [4, 0, 1, 2, 3],
                "start_minute": 510,
                "duration_minutes": 115,
            },
            {
                "label": "P2",
                "weekdays": [0, 1, 2, 3, 4],
                "start_minute": 660,
                "duration_minutes": 115,
            },
        ],
    },
}


def test_schedule_and_slot_template_round_trip(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    created = client.post("/api/v1/schedules", headers=admin.auth, json=TERM)
    assert created.status_code == 201, created.text
    schedule = created.json()
    base = f"/api/v1/schedules/{schedule['id']}"
    template = client.post(f"{base}/slot-templates", headers=admin.auth, json=PERIODS)
    assert template.status_code == 201, template.text
    assert template.json()["definition"]["slots"][0]["weekdays"] == [0, 1, 2, 3, 4]
    renamed = client.patch(base, headers=admin.auth, json={"name": "Term 1"})
    assert renamed.json()["name"] == "Term 1" and renamed.json()["end_date"] == "2027-01-15"
    assert client.get(f"{base}/slot-templates", headers=admin.auth).json() == [template.json()]
    assert client.delete(base, headers=admin.auth).status_code == 204
    assert client.get(base, headers=admin.auth).status_code == 404
    assert client.get(f"{base}/slot-templates", headers=admin.auth).status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"timezone": "Mars/Olympus"},
        {"end_date": "2027-01-10"},
        {"end_date": "2028-01-12"},
        {
            "day_parts": {
                "version": 1,
                "parts": [{"name": "am", "start_minute": 600, "end_minute": 500}],
            }
        },
        {
            "day_parts": {
                "version": 1,
                "parts": [
                    {"name": "am", "start_minute": 0, "end_minute": 60},
                    {"name": "am", "start_minute": 60, "end_minute": 120},
                ],
            }
        },
    ],
)
def test_invalid_schedules_rejected(
    client: TestClient, app: FastAPI, overrides: dict[str, object]
) -> None:
    admin = signup_and_confirm(client, app)
    response = client.post("/api/v1/schedules", headers=admin.auth, json=TERM | overrides)
    assert response.status_code == 422


def test_patch_revalidates_the_combined_dates(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    schedule = client.post("/api/v1/schedules", headers=admin.auth, json=TERM).json()
    response = client.patch(
        f"/api/v1/schedules/{schedule['id']}", headers=admin.auth, json={"start_date": "2027-02-01"}
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["body", "end_date"]


@pytest.mark.parametrize(
    "slots",
    [
        [],
        [{"label": "P1", "weekdays": [], "start_minute": 510, "duration_minutes": 60}],
        [{"label": "P1", "weekdays": [0], "start_minute": 1440, "duration_minutes": 60}],
        [
            {"label": "P1", "weekdays": [0], "start_minute": 510, "duration_minutes": 60},
            {"label": "P1", "weekdays": [1], "start_minute": 600, "duration_minutes": 60},
        ],
    ],
)
def test_invalid_slot_templates_rejected(
    client: TestClient, app: FastAPI, slots: list[object]
) -> None:
    admin = signup_and_confirm(client, app)
    schedule = client.post("/api/v1/schedules", headers=admin.auth, json=TERM).json()
    response = client.post(
        f"/api/v1/schedules/{schedule['id']}/slot-templates",
        headers=admin.auth,
        json={"name": "Bad", "definition": {"version": 1, "slots": slots}},
    )
    assert response.status_code == 422
