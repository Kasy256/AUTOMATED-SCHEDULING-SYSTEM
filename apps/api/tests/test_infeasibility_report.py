import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import add_rule, build_schedule, request_run, run_now, signup_and_confirm

pytestmark = pytest.mark.integration


def test_EXP_03_infeasible_run_stores_a_ranked_report(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    rule_id = add_rule(
        client,
        admin,
        built.schedule_id,
        "max_load",
        {"period": "week", "max_count": 0},
        hard=True,
        scope={"resource_type_ids": [built.lecturer_type_id]},
    )
    run_id = request_run(client, admin, built.schedule_id)
    assert run_now(app, run_id, admin.organisation_id) == "infeasible"
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert run["conflicts"] == [rule_id]
    report = run["infeasibility"]
    # Dropping the lecturer requirement would also do, so its pool is part of the conflict.
    assert {c["kind"] for c in report["conflicts"]} == {"rule", "requirement"}
    assert rule_id in {c["id"] for c in report["conflicts"]}
    assert report["relaxations"][0] == {
        "kind": "switch_to_soft",
        "target": rule_id,
        "text": "Make 'At most 0 activities per week' a preference instead of a hard rule",
        "fixes": True,
    }


def test_successful_run_has_no_report(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)
    assert run_now(app, run_id, admin.organisation_id) == "succeeded"
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert (run["infeasibility"], run["kind"], run["baseline_version_id"]) == (None, "solve", None)
