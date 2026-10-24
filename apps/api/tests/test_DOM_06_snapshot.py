import asyncio
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.problems.snapshot import Snapshot, build_snapshot
from cartlyf_api.tenancy import scoped_transaction
from support import APP, Account, db_url, seed_config, signup_and_confirm

pytestmark = pytest.mark.integration


def snapshot(pg: PostgresContainer, admin: Account, schedule_id: str) -> Snapshot:
    async def run() -> Snapshot:
        engine = create_async_engine(db_url(pg, *APP))
        try:
            async with scoped_transaction(engine, admin.organisation_id) as session:
                return await build_snapshot(session, admin.organisation_id, UUID(schedule_id))
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_DOM_06_same_data_same_hash(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    first = snapshot(migrated_pg, admin, ids["schedule_id"])
    assert snapshot(migrated_pg, admin, ids["schedule_id"]).hash == first.hash
    # A change the engine does not see (a display name) keeps the hash.
    client.patch(
        f"/api/v1/resources/{ids['resource_id']}", headers=admin.auth, json={"name": "Renamed"}
    )
    assert snapshot(migrated_pg, admin, ids["schedule_id"]).hash == first.hash
    # A change the engine sees changes it.
    client.patch(
        f"/api/v1/resources/{ids['resource_id']}", headers=admin.auth, json={"tags": ["phy201"]}
    )
    assert snapshot(migrated_pg, admin, ids["schedule_id"]).hash != first.hash


def test_DOM_06_snapshot_content(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    client.patch(
        base,
        headers=admin.auth,
        json={
            "day_parts": {
                "version": 1,
                "parts": [{"name": "morning", "start_minute": 480, "end_minute": 780}],
            }
        },
    )
    problem = snapshot(migrated_pg, admin, ids["schedule_id"]).problem
    assert problem.horizon_minutes == 5 * 1440
    assert [w.start for w in problem.day_windows] == [0, 1440, 2880, 4320, 5760]
    assert problem.named_windows["morning"][0].start == 480
    lecturer = next(r for r in problem.resources if r.id == ids["resource_id"])
    # Seeded: available Mon 08:00-17:00 only; unavailable Tue 08:00-10:00 (inside the blocked time).
    assert [(w.start, w.end) for w in lecturer.unavailable] == [(0, 480), (1020, 7200)]
    meeting = next(a for a in problem.activities if a.id == ids["activity_id"])
    assert meeting.candidate_starts == (540, 1440 + 540)
    generated = [a for a in problem.activities if a.series_id == ids["demand_id"]]
    assert len(generated) == 1 and generated[0].candidate_starts[0] == 510
    assert generated[0].requirements[1].fixed_resource_ids == (ids["group_resource_id"],)
    assert [c.id for c in problem.constraints] == [ids["constraint_instance_id"]]


def test_DOM_06_disabled_constraints_and_pins(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    client.put(
        f"{base}/pins/{ids['activity_id']}",
        headers=admin.auth,
        json={"start_at": "2027-01-12T09:00:00+03:00"},
    )
    client.put(
        f"{base}/constraints/{ids['constraint_instance_id']}",
        headers=admin.auth,
        json={
            "name": "Seed rule",
            "template_key": "max_load",
            "template_version": 1,
            "params": {"period": "day", "max_count": 2},
            "hard": True,
            "enabled": False,
        },
    )
    problem = snapshot(migrated_pg, admin, ids["schedule_id"]).problem
    assert problem.constraints == ()
    meeting = next(a for a in problem.activities if a.id == ids["activity_id"])
    assert meeting.pinned is not None and meeting.pinned.start == 1440 + 540


def test_DOM_06_overnight_activity_extends_the_horizon(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    base = f"/api/v1/schedules/{ids['schedule_id']}"
    night = {
        "name": "Night",
        "duration_minutes": 480,
        "candidate_starts": ["2027-01-15T23:00:00+03:00"],
    }
    assert client.post(f"{base}/activities", headers=admin.auth, json=night).status_code == 201
    problem = snapshot(migrated_pg, admin, ids["schedule_id"]).problem
    assert problem.horizon_minutes == 4 * 1440 + 23 * 60 + 480
