from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import (
    Account,
    add_rule,
    build_schedule,
    candidate_starts,
    get_version,
    signup_and_confirm,
    solve_now,
)

pytestmark = pytest.mark.integration


def _setup(client: TestClient, app: FastAPI) -> tuple[Account, str, str, list[dict[str, Any]]]:
    """One lecturer, two sessions, at most one a day: the solver puts them on different days."""
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=1, sessions=2)
    rule_id = add_rule(
        client,
        admin,
        built.schedule_id,
        "max_load",
        {"period": "day", "max_count": 1},
        hard=True,
        scope={"resource_type_ids": [built.lecturer_type_id]},
    )
    _, version_id = solve_now(client, admin, built.schedule_id)
    return admin, version_id, rule_id, get_version(client, admin, version_id)["assignments"]


def _same_day_slot(taken: datetime) -> datetime:
    return next(s for s in candidate_starts() if s.date() == taken.date() and s != taken)


def test_EXP_02_validate_move_lists_broken_rules(client: TestClient, app: FastAPI) -> None:
    admin, version_id, rule_id, (first, second) = _setup(client, app)
    to = _same_day_slot(datetime.fromisoformat(first["start_at"]))
    response = client.post(
        f"/api/v1/solution-versions/{version_id}/validate-move",
        headers=admin.auth,
        json={
            "activity_id": second["activity_id"],
            "start_at": to.isoformat(),
            "resources": second["resources"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is False
    assert rule_id in {b["constraint_id"] for b in body["broken"]}
    assert "At most 1 activity per day" in {b["rule"] for b in body["broken"]}


def test_EXP_01_explanation_names_binding_rules(client: TestClient, app: FastAPI) -> None:
    admin, version_id, rule_id, (_, second) = _setup(client, app)
    response = client.get(
        f"/api/v1/solution-versions/{version_id}/assignments/{second['activity_id']}/explanation",
        headers=admin.auth,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    binding = {b["constraint_id"]: b for b in body["binding"]}
    assert binding[rule_id]["rule"] == "At most 1 activity per day"
    assert binding[rule_id]["hard"] is True
    assert binding[rule_id]["blocks"] >= 1
    assert body["alternatives"]
    assert all("start_at" in a for a in body["alternatives"])


def test_validate_move_start_checks(client: TestClient, app: FastAPI) -> None:
    admin, version_id, _, (first, _) = _setup(client, app)
    url = f"/api/v1/solution-versions/{version_id}/validate-move"
    start = datetime.fromisoformat(first["start_at"])
    move = {"activity_id": first["activity_id"], "resources": first["resources"]}
    early = (start - timedelta(days=30)).isoformat()
    assert client.post(url, headers=admin.auth, json=move | {"start_at": early}).status_code == 422
    odd = (start + timedelta(minutes=7)).isoformat()
    response = client.post(url, headers=admin.auth, json=move | {"start_at": odd})
    assert response.status_code == 200, response.text
    assert "core:placement" in {b["constraint_id"] for b in response.json()["broken"]}


def test_explanation_of_an_unplaced_activity_is_404(client: TestClient, app: FastAPI) -> None:
    admin, version_id, _, _ = _setup(client, app)
    unknown = "00000000-0000-4000-8000-000000000000"
    response = client.get(
        f"/api/v1/solution-versions/{version_id}/assignments/{unknown}/explanation",
        headers=admin.auth,
    )
    assert response.status_code == 404


def test_explanation_checks_at_most_the_configured_alternatives(
    client: TestClient, app: FastAPI
) -> None:
    admin, version_id, _, (_, second) = _setup(client, app)
    url = f"/api/v1/solution-versions/{version_id}/assignments/{second['activity_id']}/explanation"
    whole = client.get(url, headers=admin.auth).json()
    assert whole["truncated"] is False
    app.state.settings = app.state.settings.model_copy(update={"explain_max_alternatives": 2})
    capped = client.get(url, headers=admin.auth).json()
    assert (len(capped["alternatives"]), capped["truncated"]) == (2, True)
