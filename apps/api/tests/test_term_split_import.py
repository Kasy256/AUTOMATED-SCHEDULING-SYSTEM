from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import Account, signup_and_confirm

pytestmark = pytest.mark.integration

GROUPS = "code,name,size\nBIT_S1,BIT S1,32\nBCS_S1,BCS S1,40\n"
UNITS = (
    "group,unit,subject,pair,term,room_type,weekly_minutes\n"
    "BIT_S1,BIT1103,PROG_C,BIT1103_GROUP,Term 1,Theory,240\n"
    "BIT_S1,BIT1107,PROG_C,BIT1103_GROUP,Term 1,Lab,240\n"
    "BCS_S1,BCS1103,PROG_C,BCS1103_GROUP,Term 1,Theory,240\n"
    "BCS_S1,BCS1104,PROG_C,BCS1103_GROUP,Term 1,Lab,240\n"
    "BIT_S1,BIT1104,SOFT_SKILLS,,Term 2,Theory,240\n"
    "BIT_S1,BIT1102,COMP_ORG_ARCH,,Term 1,Lab,240\n"
)


def upload(client: TestClient, admin: Account, job: dict[str, Any], csv: str) -> str:
    created = client.post("/api/v1/imports", headers=admin.auth, json=job).json()
    client.put(
        f"/api/v1/imports/{created['id']}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=csv.encode(),
    )
    return created["id"]


def setup(client: TestClient, app: FastAPI) -> tuple[Account, dict[str, Any]]:
    admin = signup_and_confirm(client, app)
    applied = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={
            "template_key": "education",
            "name": "Term 1",
            "timezone": "Africa/Kampala",
            "start_date": "2026-01-12",
            "end_date": "2026-01-16",
        },
    ).json()
    groups = upload(
        client,
        admin,
        {
            "kind": "resources",
            "resource_type_id": applied["resource_type_ids"]["student_group"],
            "filename": "groups.csv",
        },
        GROUPS,
    )
    mapping = {"kind": "resources", "code": "code", "name": "name", "size": "size"}
    url = f"/api/v1/imports/{groups}"
    assert client.post(f"{url}/dry-run", headers=admin.auth, json={"mapping": mapping}).json()[
        "report"
    ]["valid"]
    assert client.post(f"{url}/commit", headers=admin.auth).status_code == 200
    return admin, applied


def mapping(applied: dict[str, Any], **overrides: object) -> dict[str, Any]:
    types = applied["resource_type_ids"]
    return {
        "kind": "demands",
        "demand_kind": "session",
        "slot_template_id": applied["slot_template_ids"]["Teaching periods"],
        "name": "subject",
        "weekly_minutes": "weekly_minutes",
        "requirements": [
            {
                "role": "group",
                "resource_type_id": types["student_group"],
                "count_from_fixed": True,
                "fixed_codes_column": "group",
            },
            {
                "role": "room",
                "resource_type_id": types["room"],
                "attribute_columns": {"room_type": "room_type"},
            },
        ],
        "term_split": {
            "term": "Term 1",
            "term_column": "term",
            "unit_column": "unit",
            "group_column": "group",
            "merge_column": "subject",
            "pair_column": "pair",
            "prefer": {"room_type": ["Lab", "Theory"]},
        },
    } | overrides


def test_term_split_import_merges_subjects(client: TestClient, app: FastAPI) -> None:
    admin, applied = setup(client, app)
    schedule_id = applied["schedule"]["id"]
    job = upload(
        client, admin, {"kind": "demands", "schedule_id": schedule_id, "filename": "u.csv"}, UNITS
    )
    url = f"/api/v1/imports/{job}"
    dry = client.post(f"{url}/dry-run", headers=admin.auth, json={"mapping": mapping(applied)})
    assert dry.status_code == 200, dry.text
    report = dry.json()["report"]
    assert (report["valid"], report["row_count"], report["created"], report["skipped"]) == (
        True,
        6,
        2,
        1,
    )
    assert client.post(f"{url}/commit", headers=admin.auth).status_code == 200

    demands = client.get(f"/api/v1/schedules/{schedule_id}/demands", headers=admin.auth).json()
    prog_c = next(d for d in demands if d["name"] == "PROG_C")
    assert prog_c["spec"]["sessions_per_week"] == 2
    group, room = prog_c["spec"]["requirements"]
    assert len(group["fixed_resource_ids"]) == 2
    # Exactly the merged groups: the solver must not add other groups to the class.
    assert (group["count_min"], group["count_max"]) == (2, 2)
    assert room["attrs"] == [{"attr": "room_type", "op": "eq", "value": "Lab"}]
    assert {d["name"] for d in demands} == {"PROG_C", "COMP_ORG_ARCH"}


def test_term_split_reports_row_errors(client: TestClient, app: FastAPI) -> None:
    admin, applied = setup(client, app)
    schedule_id = applied["schedule"]["id"]
    csv = (
        "group,unit,subject,pair,term,room_type,weekly_minutes\n"
        "BIT_S1,U1,S1,,Term 1,Lab,lots\n"
        "NOPE,U2,S2,,Term 1,Lab,240\n"
        "BIT_S1,U3,S3,,,Lab,240\n"
    )
    job = upload(
        client, admin, {"kind": "demands", "schedule_id": schedule_id, "filename": "u.csv"}, csv
    )
    body = client.post(
        f"/api/v1/imports/{job}/dry-run", headers=admin.auth, json={"mapping": mapping(applied)}
    ).json()
    errors = {(e["row"], e["column"]) for e in body["report"]["errors"]}
    assert errors == {(4, "term")}

    fixed = csv.replace("BIT_S1,U3,S3,,,Lab,240", "BIT_S1,U3,S3,,Term 1,Lab,240")
    job = upload(
        client, admin, {"kind": "demands", "schedule_id": schedule_id, "filename": "u.csv"}, fixed
    )
    body = client.post(
        f"/api/v1/imports/{job}/dry-run", headers=admin.auth, json={"mapping": mapping(applied)}
    ).json()
    errors = {(e["row"], e["column"]) for e in body["report"]["errors"]}
    assert errors == {(2, "weekly_minutes"), (3, "group")}


def test_weekly_minutes_or_sessions_is_required(client: TestClient, app: FastAPI) -> None:
    admin, applied = setup(client, app)
    schedule_id = applied["schedule"]["id"]
    job = upload(
        client, admin, {"kind": "demands", "schedule_id": schedule_id, "filename": "u.csv"}, UNITS
    )
    response = client.post(
        f"/api/v1/imports/{job}/dry-run",
        headers=admin.auth,
        json={"mapping": mapping(applied, weekly_minutes=None)},
    )
    assert response.status_code == 422
