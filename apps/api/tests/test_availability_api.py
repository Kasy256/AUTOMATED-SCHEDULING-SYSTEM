import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


def test_rules_and_exceptions_round_trip(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    resource = seed_config(client, admin)["resource_id"]
    base = f"/api/v1/resources/{resource}"
    rule = client.post(
        f"{base}/availability-rules",
        headers=admin.auth,
        json={"kind": "available", "weekday": 0, "start_minute": 480, "end_minute": 1020},
    )
    assert rule.status_code == 201, rule.text
    leave = client.post(
        f"{base}/availability-exceptions",
        headers=admin.auth,
        json={
            "kind": "unavailable",
            "starts_at": "2027-01-11T08:00:00+03:00",
            "ends_at": "2027-01-11T12:00:00+03:00",
            "reason": "Leave",
        },
    )
    assert leave.status_code == 201, leave.text
    assert leave.json()["starts_at"] == "2027-01-11T05:00:00Z"
    rules = client.get(f"{base}/availability-rules", headers=admin.auth).json()
    assert rule.json()["id"] in [r["id"] for r in rules]
    gone = client.delete(f"{base}/availability-rules/{rule.json()['id']}", headers=admin.auth)
    assert gone.status_code == 204


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "availability-rules",
            {"kind": "available", "weekday": 7, "start_minute": 0, "end_minute": 60},
        ),
        (
            "availability-rules",
            {"kind": "available", "weekday": 0, "start_minute": 600, "end_minute": 600},
        ),
        ("availability-rules", {"kind": "busy", "weekday": 0, "start_minute": 0, "end_minute": 60}),
        (
            "availability-exceptions",
            {
                "kind": "unavailable",
                "starts_at": "2027-01-11T08:00:00",
                "ends_at": "2027-01-11T09:00:00",
            },
        ),
        (
            "availability-exceptions",
            {
                "kind": "unavailable",
                "starts_at": "2027-01-11T09:00:00Z",
                "ends_at": "2027-01-11T08:00:00Z",
            },
        ),
    ],
)
def test_invalid_availability_is_rejected(
    client: TestClient, app: FastAPI, path: str, body: dict[str, object]
) -> None:
    admin = signup_and_confirm(client, app)
    resource = seed_config(client, admin)["resource_id"]
    response = client.post(f"/api/v1/resources/{resource}/{path}", headers=admin.auth, json=body)
    assert response.status_code == 422


def test_rule_of_another_resource_is_not_found(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    other = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": ids["resource_type_id"], "code": "LEC-OTHER", "name": "Other"},
    ).json()["id"]
    rule_url = (
        f"/api/v1/resources/{ids['resource_id']}/availability-rules/{ids['availability_rule_id']}"
    )
    wrong_parent = rule_url.replace(ids["resource_id"], other)
    assert client.delete(wrong_parent, headers=admin.auth).status_code == 404
    assert client.delete(rule_url, headers=admin.auth).status_code == 204
