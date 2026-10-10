import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import Account, execute, seed_config, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration
CSV = b"Code,Name\nIMP-1,Imported one\n"


def uploaded_import(client: TestClient, admin: Account, type_id: str) -> str:
    job = client.post(
        "/api/v1/imports",
        headers=admin.auth,
        json={"kind": "resources", "resource_type_id": type_id, "filename": "staff.csv"},
    )
    assert job.status_code == 201, job.text
    import_id = job.json()["id"]
    upload = client.put(
        f"/api/v1/imports/{import_id}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=CSV,
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["columns"] == ["Code", "Name"] and upload.json()["status"] == "uploaded"
    return import_id


def test_TEN_05_owner_downloads_other_orgs_and_bad_tokens_cannot(
    client: TestClient, app: FastAPI
) -> None:
    a = signup_and_confirm(client, app, org_name="Files A")
    b = signup_and_confirm(client, app, org_name="Files B")
    import_id = uploaded_import(client, a, seed_config(client, a)["resource_type_id"])
    url = f"/api/v1/imports/{import_id}/file"
    own = client.get(url, headers=a.auth)
    assert own.status_code == 200 and own.content == CSV
    assert own.headers["content-type"].startswith("text/csv")
    assert 'filename="staff.csv"' in own.headers["content-disposition"]
    assert client.get(url, headers=b.auth).status_code == 404
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_TEN_05_foreign_object_key_is_refused(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    a = signup_and_confirm(client, app, org_name="Keys A")
    b = signup_and_confirm(client, app, org_name="Keys B")
    import_id = uploaded_import(client, a, seed_config(client, a)["resource_type_id"])
    execute(
        superuser_url(migrated_pg),
        f"UPDATE import_job SET object_key = 'org/{b.organisation_id}/imports/x/source.csv' "
        f"WHERE id = '{import_id}'",
    )
    assert client.get(f"/api/v1/imports/{import_id}/file", headers=a.auth).status_code == 404


def test_upload_limits(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    type_id = seed_config(client, admin)["resource_type_id"]
    job = client.post(
        "/api/v1/imports",
        headers=admin.auth,
        json={"kind": "resources", "resource_type_id": type_id, "filename": "x.csv"},
    ).json()
    url = f"/api/v1/imports/{job['id']}/file"
    assert client.get(url, headers=admin.auth).status_code == 404  # nothing uploaded yet
    bad = client.put(url, headers=admin.auth | {"Content-Type": "text/csv"}, content=b"\xff\xfe")
    assert bad.status_code == 422
    huge = b"Code\n" + b"X" * (app.state.settings.import_max_bytes + 1)
    too_big = client.put(url, headers=admin.auth | {"Content-Type": "text/csv"}, content=huge)
    assert too_big.status_code == 413


def test_import_target_must_match_kind(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    wrong = {"kind": "demands", "resource_type_id": ids["resource_type_id"], "filename": "d.csv"}
    assert client.post("/api/v1/imports", headers=admin.auth, json=wrong).status_code == 422
