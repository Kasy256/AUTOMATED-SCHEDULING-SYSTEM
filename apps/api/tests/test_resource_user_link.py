import asyncio
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.tenancy import scoped_transaction
from support import APP, Account, add_member, db_url, fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def user_id_of(client: TestClient, account: Account) -> str:
    return client.get("/api/v1/auth/me", headers=account.auth).json()["user_id"]


# Any: response JSON.
def make_resource(
    client: TestClient, admin: Account, kind: str = "person", code: str = "LEC-1"
) -> dict[str, Any]:
    rtype = client.post(
        "/api/v1/resource-types",
        headers=admin.auth,
        json={
            "key": f"{kind}_{code.lower().replace('-', '_')}",
            "name": kind.title(),
            "kind": kind,
        },
    )
    assert rtype.status_code == 201, rtype.text
    response = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": rtype.json()["id"], "code": code, "name": code},
    )
    assert response.status_code == 201, response.text
    return response.json()


def link(client: TestClient, admin: Account, resource_id: str, user_id: str | None) -> Any:
    return client.patch(
        f"/api/v1/resources/{resource_id}", headers=admin.auth, json={"user_id": user_id}
    )


def test_link_resource_to_member(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    lecturer = make_resource(client, admin)
    assert lecturer["user_id"] is None
    member_id = user_id_of(client, member)
    response = link(client, admin, lecturer["id"], member_id)
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == member_id
    fetched = client.get(f"/api/v1/resources/{lecturer['id']}", headers=admin.auth)
    assert fetched.json()["user_id"] == member_id
    cleared = link(client, admin, lecturer["id"], None)
    assert cleared.status_code == 200 and cleared.json()["user_id"] is None


def test_create_with_link(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    rtype = client.post(
        "/api/v1/resource-types",
        headers=admin.auth,
        json={"key": "lecturer", "name": "Lecturer", "kind": "person"},
    ).json()
    own = user_id_of(client, admin)
    response = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": rtype["id"], "code": "L1", "name": "L1", "user_id": own},
    )
    assert response.status_code == 201, response.text
    assert response.json()["user_id"] == own


def test_link_requires_active_member_of_this_org(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app, org_name="Org A")
    other = signup_and_confirm(client, app, org_name="Org B")
    lecturer = make_resource(client, admin)
    response = link(client, admin, lecturer["id"], user_id_of(client, other))
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown user"


def test_link_only_person_kind(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    room = make_resource(client, admin, kind="space", code="LT1")
    response = link(client, admin, room["id"], user_id_of(client, admin))
    assert response.status_code == 422
    assert [e["loc"] for e in response.json()["errors"]] == [["body", "user_id"]]


def test_one_resource_per_user(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    first = make_resource(client, admin, code="LEC-1")
    second = make_resource(client, admin, code="LEC-2")
    own = user_id_of(client, admin)
    assert link(client, admin, first["id"], own).status_code == 200
    response = link(client, admin, second["id"], own)
    assert response.status_code == 409
    assert link(client, admin, first["id"], own).status_code == 200


def test_link_change_is_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    lecturer = make_resource(client, admin)
    assert link(client, admin, lecturer["id"], user_id_of(client, admin)).status_code == 200
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT details FROM audit_log WHERE action = 'resource.updated' "
        f"AND target_id = '{lecturer['id']}'",
    )
    assert rows and "user_id" in rows[0][0]["fields"]


def test_repository_lookups(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    lecturer = make_resource(client, admin)
    own = user_id_of(client, admin)
    assert link(client, admin, lecturer["id"], own).status_code == 200
    org = admin.organisation_id

    async def run() -> tuple[list[UUID], dict[UUID, UUID]]:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            async with scoped_transaction(engine, org) as session:
                return (
                    await resources_repo.resource_ids_for_user(session, org, UUID(own)),
                    await resources_repo.users_for_resources(session, org, [UUID(lecturer["id"])]),
                )
        finally:
            await engine.dispose()

    ids, users = asyncio.run(run())
    assert ids == [UUID(lecturer["id"])]
    assert users == {UUID(lecturer["id"]): UUID(own)}
