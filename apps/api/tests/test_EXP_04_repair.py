from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    Account,
    add_rule,
    build_schedule,
    fetch,
    get_version,
    publish,
    run_now,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration

KAMPALA = ZoneInfo("Africa/Kampala")
FREEZE = datetime(2027, 1, 13, tzinfo=KAMPALA)  # for requests refused before freezing
WEEK_END = datetime(2027, 1, 16, tzinfo=KAMPALA)
STABILITY: dict[str, object] = {"per_change": 1, "per_resource_change": 1}


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _repair(client: TestClient, admin: Account, schedule_id: str, freeze: datetime) -> Any:
    return client.post(
        f"/api/v1/schedules/{schedule_id}/repairs",
        headers=admin.auth,
        json={"freeze_before": freeze.isoformat()},
    )


def _freeze(assignments: list[dict[str, Any]]) -> datetime:
    """Midnight of the second day with assignments, so both a past and a future exist."""
    days = sorted({_at(a["start_at"]).astimezone(KAMPALA).date() for a in assignments})
    assert len(days) >= 2, days
    return datetime(days[1].year, days[1].month, days[1].day, tzinfo=KAMPALA)


def _published(client: TestClient, app: FastAPI) -> tuple[Account, str, str]:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=2, rooms=2, groups=2, demands=3, sessions=3)
    add_rule(client, admin, built.schedule_id, "stability", STABILITY, weight=10)
    _, version_id = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, version_id).status_code == 200
    return admin, built.schedule_id, version_id


def _unavailable(client: TestClient, admin: Account, resource_id: str, start: datetime) -> None:
    response = client.post(
        f"/api/v1/resources/{resource_id}/availability-exceptions",
        headers=admin.auth,
        json={
            "kind": "unavailable",
            "starts_at": start.isoformat(),
            "ends_at": WEEK_END.isoformat(),
        },
    )
    assert response.status_code == 201, response.text


def test_EXP_04_repair_changes_little_and_keeps_the_past(client: TestClient, app: FastAPI) -> None:
    admin, schedule_id, published_id = _published(client, app)
    baseline = get_version(client, admin, published_id)["assignments"]
    freeze = _freeze(baseline)
    later = [a for a in baseline if _at(a["start_at"]) >= freeze]
    lecturer = later[0]["resources"]["lecturer"][0]
    hit = [a for a in later if lecturer in a["resources"]["lecturer"]]
    _unavailable(client, admin, lecturer, freeze)

    response = _repair(client, admin, schedule_id, freeze)
    assert response.status_code == 202, response.text
    run = response.json()
    assert (run["kind"], run["baseline_version_id"]) == ("repair", published_id)
    assert run_now(app, run["id"], admin.organisation_id) == "succeeded"
    draft_id = client.get(f"/api/v1/solves/{run['id']}", headers=admin.auth).json()["version_id"]
    draft = get_version(client, admin, draft_id)
    assert draft["parent_version_id"] == published_id

    diff = client.get(
        f"/api/v1/solution-versions/{published_id}/diff/{draft_id}", headers=admin.auth
    ).json()
    changed = diff["moved"] + diff["reassigned"]
    assert (diff["added"], diff["removed"]) == ([], [])
    assert 1 <= len(changed) <= len(hit)  # P9: the documented bound
    assert all(_at(c["before"]["start_at"]) >= freeze for c in changed)
    assert all(_at(c["after"]["start_at"]) >= freeze for c in changed)
    assert not [
        a
        for a in draft["assignments"]
        if _at(a["start_at"]) >= freeze and lecturer in a["resources"]["lecturer"]
    ]


def test_repair_needs_a_published_version(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    add_rule(client, admin, built.schedule_id, "stability", STABILITY, weight=1)
    assert _repair(client, admin, built.schedule_id, FREEZE).status_code == 409


def test_repair_needs_a_stability_rule(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version_id = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, version_id).status_code == 200
    assert _repair(client, admin, built.schedule_id, FREEZE).status_code == 422


def test_repair_conflicting_with_the_frozen_past_is_infeasible_with_a_report(
    client: TestClient, app: FastAPI
) -> None:
    admin, schedule_id, published_id = _published(client, app)
    baseline = get_version(client, admin, published_id)["assignments"]
    freeze = _freeze(baseline)
    past = next(a for a in baseline if _at(a["start_at"]) < freeze)
    lecturer = past["resources"]["lecturer"][0]
    _unavailable(client, admin, lecturer, _at(past["start_at"]))

    run = _repair(client, admin, schedule_id, freeze).json()
    assert run_now(app, run["id"], admin.organisation_id) == "infeasible"
    report = client.get(f"/api/v1/solves/{run['id']}", headers=admin.auth).json()["infeasibility"]
    assert {c["kind"] for c in report["conflicts"]} >= {"pin", "unavailable"}


def test_repair_rejects_a_frozen_assignment_that_no_longer_fits(
    client: TestClient, app: FastAPI
) -> None:
    admin, schedule_id, published_id = _published(client, app)
    baseline = get_version(client, admin, published_id)["assignments"]
    freeze = _freeze(baseline)
    past = next(a for a in baseline if _at(a["start_at"]) < freeze)
    room = past["resources"]["room"][0]
    assert client.delete(f"/api/v1/resources/{room}", headers=admin.auth).status_code == 204
    response = _repair(client, admin, schedule_id, freeze)
    assert response.status_code == 422
    assert room not in response.text


def test_repair_never_offers_a_start_before_the_freeze(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin, schedule_id, published_id = _published(client, app)
    freeze = _freeze(get_version(client, admin, published_id)["assignments"])
    run = _repair(client, admin, schedule_id, freeze).json()
    ((problem, origin),) = fetch(
        superuser_url(migrated_pg),
        f"SELECT problem, horizon_origin FROM solve_run WHERE id = '{run['id']}'",
    )
    cutoff = (freeze - origin).total_seconds() // 60
    for activity in problem["activities"]:
        if activity["pinned"] is None:
            assert min(activity["candidate_starts"]) >= cutoff, activity["id"]
