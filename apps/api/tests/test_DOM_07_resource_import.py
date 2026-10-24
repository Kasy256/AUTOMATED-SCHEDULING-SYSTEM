from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import Account, seed_config, signup_and_confirm

pytestmark = pytest.mark.integration
MAPPING = {
    "kind": "resources",
    "code": "Code",
    "name": "Name",
    "tags": "Subjects",
    "attributes": {"employment": "Employment"},
}


def start(client: TestClient, admin: Account, type_id: str, csv: str) -> str:
    job = client.post(
        "/api/v1/imports",
        headers=admin.auth,
        json={"kind": "resources", "resource_type_id": type_id, "filename": "l.csv"},
    ).json()
    response = client.put(
        f"/api/v1/imports/{job['id']}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=csv.encode(),
    )
    assert response.status_code == 200, response.text
    return job["id"]


def codes(client: TestClient, admin: Account) -> set[str]:
    return {r["code"] for r in client.get("/api/v1/resources", headers=admin.auth).json()}


# Any: response JSON.
def dry_run(client: TestClient, admin: Account, import_id: str, mapping: dict[str, Any]) -> Any:
    return client.post(
        f"/api/v1/imports/{import_id}/dry-run", headers=admin.auth, json={"mapping": mapping}
    )


def test_DOM_07_mapped_csv_creates_resources(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    type_id = seed_config(client, admin)["resource_type_id"]
    before = codes(client, admin)
    csv = "Code,Name,Subjects,Employment\nL1,Dr A,math101;phy201,full_time\nL2,Dr B,,part_time\n"
    import_id = start(client, admin, type_id, csv)
    report = dry_run(client, admin, import_id, MAPPING)
    assert report.status_code == 200, report.text
    assert report.json()["status"] == "validated"
    assert report.json()["report"] == {
        "valid": True,
        "row_count": 2,
        "created": 2,
        "errors": [],
        "error_count": 0,
        "feasibility": [],
        "skipped": 0,
    }
    assert codes(client, admin) == before  # dry run wrote nothing
    committed = client.post(f"/api/v1/imports/{import_id}/commit", headers=admin.auth)
    assert committed.status_code == 200 and committed.json()["status"] == "committed"
    assert codes(client, admin) == before | {"L1", "L2"}
    l1 = next(
        r for r in client.get("/api/v1/resources", headers=admin.auth).json() if r["code"] == "L1"
    )
    assert l1["tags"] == ["math101", "phy201"] and l1["attributes"] == {"employment": "full_time"}
    again = client.post(f"/api/v1/imports/{import_id}/commit", headers=admin.auth)
    assert again.status_code == 409


def test_DOM_07_one_bad_row_writes_nothing(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    type_id = seed_config(client, admin)["resource_type_id"]
    before = codes(client, admin)
    csv = (
        "Code,Name,Subjects,Employment\n"
        "L3,Dr C,,full_time\nL4,Dr D,,contractor\nL3,Dr E,,part_time\nLEC-001,Dup,,full_time\n"
    )
    import_id = start(client, admin, type_id, csv)
    body = dry_run(client, admin, import_id, MAPPING).json()
    assert body["status"] == "invalid"
    errors = {(e["row"], e["column"]) for e in body["report"]["errors"]}
    assert errors == {(3, "Employment"), (4, "Code"), (5, "Code")}
    assert "contractor" not in str(body)
    assert client.post(f"/api/v1/imports/{import_id}/commit", headers=admin.auth).status_code == 409
    assert codes(client, admin) == before


def test_DOM_07_commit_revalidates_against_current_data(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    type_id = seed_config(client, admin)["resource_type_id"]
    import_id = start(client, admin, type_id, "Code,Name,Subjects,Employment\nL9,Dr Z,,full_time\n")
    assert dry_run(client, admin, import_id, MAPPING).json()["status"] == "validated"
    client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": type_id, "code": "L9", "name": "Taken"},
    )
    response = client.post(f"/api/v1/imports/{import_id}/commit", headers=admin.auth)
    assert response.status_code == 409
    assert response.json()["report"]["errors"][0]["row"] == 2
    names = [r["name"] for r in client.get("/api/v1/resources", headers=admin.auth).json()]
    assert "Dr Z" not in names


def test_DOM_07_mapping_must_name_real_columns(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    type_id = seed_config(client, admin)["resource_type_id"]
    import_id = start(client, admin, type_id, "Code,Name\nL1,Dr A\n")
    response = dry_run(client, admin, import_id, MAPPING)
    assert response.status_code == 422
    locs = {tuple(e["loc"]) for e in response.json()["errors"]}
    assert ("body", "mapping", "tags") in locs
    assert ("body", "mapping", "attributes", "employment") in locs
