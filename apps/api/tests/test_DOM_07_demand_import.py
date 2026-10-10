import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import Account, seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


def mapping(ids: dict[str, str]) -> dict[str, object]:
    return {
        "kind": "demands",
        "demand_kind": "session",
        "slot_template_id": ids["slot_template_id"],
        "name": "Course",
        "sessions_per_week": "Sessions",
        "slot_labels": "Periods",
        "requirements": [
            {
                "role": "lecturer",
                "resource_type_id": ids["resource_type_id"],
                "tags_column": "Subject",
            },
            {"role": "group", "fixed_codes_column": "Groups"},
        ],
    }


def start(client: TestClient, admin: Account, schedule_id: str, csv: str) -> str:
    job = client.post(
        "/api/v1/imports",
        headers=admin.auth,
        json={"kind": "demands", "schedule_id": schedule_id, "filename": "d.csv"},
    ).json()
    client.put(
        f"/api/v1/imports/{job['id']}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=csv.encode(),
    )
    return job["id"]


def demand_names(client: TestClient, admin: Account, schedule_id: str) -> set[str]:
    demands = client.get(f"/api/v1/schedules/{schedule_id}/demands", headers=admin.auth).json()
    return {d["name"] for d in demands}


def test_DOM_07_demand_import_with_feasibility_report(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    before = demand_names(client, admin, ids["schedule_id"])
    csv = (
        "Course,Sessions,Periods,Subject,Groups\nCalculus,1,P1,math101,LEC-001\nQuantum,1,,qm999,\n"
    )
    import_id = start(client, admin, ids["schedule_id"], csv)
    dry = client.post(
        f"/api/v1/imports/{import_id}/dry-run", headers=admin.auth, json={"mapping": mapping(ids)}
    )
    assert dry.status_code == 200, dry.text
    report = dry.json()["report"]
    assert report["valid"] is True and report["created"] == 2
    # Nobody has tag qm999: the feasibility check flags it, but it does not block the import.
    assert "unfillable_requirement" in {issue["code"] for issue in report["feasibility"]}
    assert demand_names(client, admin, ids["schedule_id"]) == before
    assert client.post(f"/api/v1/imports/{import_id}/commit", headers=admin.auth).status_code == 200
    assert demand_names(client, admin, ids["schedule_id"]) == before | {"Calculus", "Quantum"}


def test_DOM_07_demand_row_errors(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    csv = (
        "Course,Sessions,Periods,Subject,Groups\n"
        "Good,1,,math101,\nBad count,zero,,math101,\nBad label,1,P9,math101,\n"
        "Bad group,1,,math101,NOPE\n"
    )
    import_id = start(client, admin, ids["schedule_id"], csv)
    body = client.post(
        f"/api/v1/imports/{import_id}/dry-run", headers=admin.auth, json={"mapping": mapping(ids)}
    ).json()
    assert body["status"] == "invalid"
    assert {(e["row"], e["column"]) for e in body["report"]["errors"]} == {
        (3, "Sessions"),
        (4, "Periods"),
        (5, "Groups"),
    }
    assert "Good" not in demand_names(client, admin, ids["schedule_id"])


def test_DOM_07_mapping_kind_must_match_job(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    import_id = start(client, admin, ids["schedule_id"], "Course\nX\n")
    wrong = {"mapping": {"kind": "resources", "code": "Course", "name": "Course"}}
    response = client.post(f"/api/v1/imports/{import_id}/dry-run", headers=admin.auth, json=wrong)
    assert response.status_code == 422
