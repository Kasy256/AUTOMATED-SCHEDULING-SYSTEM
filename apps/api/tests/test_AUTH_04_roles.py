import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import add_member, signup_and_confirm

pytestmark = pytest.mark.integration


def test_AUTH_04_member_plus_planner_gets_union(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member_only = add_member(client, app, admin, ["member"])
    both = add_member(client, app, admin, ["member", "planner"])
    assert client.get("/api/v1/members", headers=member_only.auth).status_code == 403
    listed = client.get("/api/v1/members", headers=both.auth)
    assert listed.status_code == 200
    mine = next(m for m in listed.json() if m["email"] == both.email)
    assert mine["roles"] == ["member", "planner"]


def test_AUTH_04_role_change_takes_effect_immediately(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    planner = add_member(client, app, admin, ["planner"])
    members = client.get("/api/v1/members", headers=planner.auth).json()
    membership_id = next(m["membership_id"] for m in members if m["email"] == planner.email)
    changed = client.put(
        f"/api/v1/members/{membership_id}/roles", headers=admin.auth, json={"roles": ["viewer"]}
    )
    assert changed.status_code == 200
    assert changed.json()["roles"] == ["viewer"]
    assert client.get("/api/v1/members", headers=planner.auth).status_code == 403
