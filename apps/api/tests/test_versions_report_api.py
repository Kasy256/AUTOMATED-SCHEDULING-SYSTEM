import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import add_member, build_schedule, signup_and_confirm, solve_now

pytestmark = pytest.mark.integration


def test_report_for_a_solved_version(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=2, demands=3, sessions=1)
    _, version = solve_now(client, admin, built.schedule_id)
    response = client.get(f"/api/v1/solution-versions/{version}/report", headers=admin.auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version_id"] == version
    assert sum(x["activities"] for x in body["load"]) == 3
    kinds = {f["type_key"].split("_")[0] for f in body["fairness"]}
    assert kinds >= {"lecturer", "room"}
    assert body["coverage_gaps"] == []
    assert all(0 <= u["ratio"] <= 1 for u in body["utilisation"])


def test_viewer_reads_member_only_is_forbidden(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    viewer = add_member(client, app, admin, ["viewer"])
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    url = f"/api/v1/solution-versions/{version}/report"
    assert client.get(url, headers=viewer.auth).status_code == 200
    assert client.get(url, headers=member.auth).status_code == 403


def test_report_of_other_orgs_version_is_404(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    other = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    url = f"/api/v1/solution-versions/{version}/report"
    assert client.get(url, headers=other.auth).status_code == 404
