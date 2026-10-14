import csv
import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.versions.export import ExportRow, csv_rows, safe_cell
from support import add_member, build_schedule, publish, signup_and_confirm, solve_now

HEADER = ["activity_id", "activity", "start", "end", "role", "resource_code", "resource"]


@pytest.mark.parametrize("lead", ["=", "+", "-", "@", "\t", "\r"])
def test_safe_cell_neutralises_formulas(lead: str) -> None:
    assert safe_cell(f"{lead}SUM(A1)") == f"'{lead}SUM(A1)"


def test_safe_cell_leaves_plain_text_alone() -> None:
    assert safe_cell("Maths 101") == "Maths 101"
    assert safe_cell("") == ""


def test_csv_rows_sorts_and_neutralises_every_cell() -> None:
    start = datetime(2027, 1, 11, 6, 0, tzinfo=UTC)
    end = datetime(2027, 1, 11, 7, 0, tzinfo=UTC)
    rows = [
        ExportRow("a2", "=cmd", start, end, "room", "R-1", "Room"),
        ExportRow("a1", "Algebra", start, end, "lecturer", "-L", "Lec"),
    ]
    lines = list(csv_rows(rows, ZoneInfo("Africa/Kampala")))
    parsed = list(csv.reader(io.StringIO("".join(lines))))
    assert parsed[0] == HEADER
    assert parsed[1][1] == "'=cmd"
    assert parsed[1][2] == "2027-01-11T09:00:00+03:00"
    assert parsed[2][1] == "Algebra"
    assert parsed[2][5] == "'-L"


def test_export_csv_has_one_row_per_resource_in_schedule_timezone(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2, sessions=1)
    _, version = solve_now(client, admin, built.schedule_id)
    detail = client.get(f"/api/v1/solution-versions/{version}", headers=admin.auth).json()
    resource_rows = sum(len(ids) for a in detail["assignments"] for ids in a["resources"].values())

    response = client.get(f"/api/v1/solution-versions/{version}/export.csv", headers=admin.auth)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == HEADER
    assert len(rows) - 1 == resource_rows
    assert all(r[2].endswith("+03:00") and r[3].endswith("+03:00") for r in rows[1:])
    assert {r[1].split(" W")[0] for r in rows[1:]} == {"Course 0", "Course 1"}
    assert {r[5] for r in rows[1:] if r[4] == "lecturer"} == {"LECTURER-0"}
    assert [r[2] for r in rows[1:]] == sorted(r[2] for r in rows[1:])


def test_export_of_other_orgs_version_is_404(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    other = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    response = client.get(f"/api/v1/solution-versions/{version}/export.csv", headers=other.auth)
    assert response.status_code == 404


def test_member_export_contains_only_own_rows(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin, lecturers=2, demands=4, sessions=1)
    _, version = solve_now(client, admin, built.schedule_id)
    url = f"/api/v1/solution-versions/{version}/export.csv"
    me = client.get("/api/v1/auth/me", headers=member.auth).json()["user_id"]
    full = client.get(f"/api/v1/solution-versions/{version}", headers=admin.auth).json()
    mine = full["assignments"][0]["resources"]["lecturer"][0]
    patched = client.patch(f"/api/v1/resources/{mine}", headers=admin.auth, json={"user_id": me})
    assert patched.status_code == 200, patched.text

    assert client.get(url, headers=member.auth).status_code == 404
    assert publish(client, admin, version).status_code == 200

    response = client.get(url, headers=member.auth)
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text)))[1:]
    expected = {a["activity_id"] for a in full["assignments"] if mine in a["resources"]["lecturer"]}
    assert expected
    assert {r[0] for r in rows} == expected
    admin_rows = list(csv.reader(io.StringIO(client.get(url, headers=admin.auth).text)))[1:]
    assert {r[4] for r in rows} == {"lecturer", "room", "group"}
    assert len(rows) <= len(admin_rows)
    assert {tuple(r) for r in rows} == {tuple(r) for r in admin_rows if r[0] in expected}

    unlinked = add_member(client, app, admin, ["member"])
    empty = client.get(url, headers=unlinked.auth)
    assert empty.status_code == 200
    assert list(csv.reader(io.StringIO(empty.text))) == [HEADER]


def test_export_content_disposition_filename_is_sanitised(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    renamed = client.patch(
        f"/api/v1/schedules/{built.schedule_id}",
        headers=admin.auth,
        json={"name": 'Term "1"/../é\r\nX'},
    )
    assert renamed.status_code == 200, renamed.text
    _, version = solve_now(client, admin, built.schedule_id)
    response = client.get(f"/api/v1/solution-versions/{version}/export.csv", headers=admin.auth)
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="')
    filename = disposition.split('"')[1]
    assert filename.endswith("-v1.csv")
    assert all(c.isascii() and (c.isalnum() or c in "._-") for c in filename)
    assert "\n" not in disposition and "/" not in filename
