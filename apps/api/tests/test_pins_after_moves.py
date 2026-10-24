from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import build_schedule, free_start, get_version, move, signup_and_confirm, solve_now

pytestmark = pytest.mark.integration


def test_a_move_becomes_a_draft_and_a_pin_holds_in_the_next_solve(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version_id = solve_now(client, admin, built.schedule_id)
    assignments = get_version(client, admin, version_id)["assignments"]
    target, to = assignments[0], free_start(assignments)
    moved = move(client, admin, version_id, target, to)
    assert moved.status_code == 201, moved.text
    assert moved.json()["parent_version_id"] == version_id
    pin = client.put(
        f"/api/v1/schedules/{built.schedule_id}/pins/{target['activity_id']}",
        headers=admin.auth,
        json={"start_at": to.isoformat()},
    )
    assert pin.status_code == 200, pin.text
    _, next_id = solve_now(client, admin, built.schedule_id)
    placed = {a["activity_id"]: a for a in get_version(client, admin, next_id)["assignments"]}
    assert datetime.fromisoformat(placed[target["activity_id"]]["start_at"]) == to
