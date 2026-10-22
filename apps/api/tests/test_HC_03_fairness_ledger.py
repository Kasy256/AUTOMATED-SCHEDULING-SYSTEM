import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.fairness.models import FairnessLedgerRow
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_engine.domain import Problem
from support import (
    APP,
    Account,
    db_url,
    execute,
    fetch,
    get_version,
    publish,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration

WEEK_A = ("2027-01-04", "2027-01-10")
WEEK_B = ("2027-01-11", "2027-01-17")


@dataclass(frozen=True)
class Roster:
    schedule_id: str
    nights_rule_id: str


@dataclass(frozen=True)
class Ward:
    admin: Account
    nurse_type_id: str
    nurse_ids: list[str]


# Any: response JSON is untyped; tests read values from it.
def _post(client: TestClient, admin: Account, path: str, body: object) -> dict[str, Any]:
    response = client.post(path, headers=admin.auth, json=body)
    assert response.status_code == 201, f"{path}: {response.text}"
    return response.json()


def roster(client: TestClient, admin: Account, week: tuple[str, str]) -> tuple[Roster, str]:
    """A healthcare-template schedule with one night-coverage demand for one RN."""
    created = _post(
        client,
        admin,
        "/api/v1/schedules/from-template",
        {
            "template_key": "healthcare",
            "name": f"Ward {week[0]}",
            "timezone": "Africa/Kampala",
            "start_date": week[0],
            "end_date": week[1],
        },
    )
    schedule_id: str = created["schedule"]["id"]
    nurse_type: str = created["resource_type_ids"]["nurse"]
    slots: dict[str, str] = created["slot_template_ids"]
    _post(
        client,
        admin,
        f"/api/v1/schedules/{schedule_id}/demands",
        {
            "name": "Ward night",
            "slot_template_id": slots["Shifts"],
            "spec": {
                "kind": "coverage",
                "slot_labels": ["Night"],
                "requirements": [{"role": "nurse", "resource_type_id": nurse_type, "tags": ["RN"]}],
            },
        },
    )
    rules = client.get(f"/api/v1/schedules/{schedule_id}/constraints", headers=admin.auth).json()
    [nights] = [
        r["id"]
        for r in rules
        if r["template_key"] == "fairness"
        and r["params"]["counter"] == "nights"
        and r["scope"]["tags"] == ["RN"]
    ]
    return Roster(schedule_id, nights), nurse_type


def ward(client: TestClient, app: FastAPI, nurses: int = 3) -> tuple[Ward, Roster, Roster]:
    admin = signup_and_confirm(client, app)
    a, nurse_type = roster(client, admin, WEEK_A)
    b, _ = roster(client, admin, WEEK_B)
    ids = [
        str(
            _post(
                client,
                admin,
                "/api/v1/resources",
                {
                    "resource_type_id": nurse_type,
                    "code": f"RN-{i}",
                    "name": f"Nurse {i}",
                    "tags": ["RN"],
                    "attributes": {"contract_minutes_per_week": 2400},
                },
            )["id"]
        )
        for i in range(nurses)
    ]
    return Ward(admin, nurse_type, ids), a, b


def night_counts(client: TestClient, admin: Account, version_id: str) -> dict[str, int]:
    assignments = get_version(client, admin, version_id)["assignments"]
    return dict(Counter(r for a in assignments for r in a["resources"]["nurse"]))


def ledger(pg: PostgresContainer, schedule_id: str, counter: str = "nights") -> dict[str, int]:
    rows = fetch(
        superuser_url(pg),
        "SELECT resource_id, sum(count) FROM fairness_ledger "
        f"WHERE schedule_id = '{schedule_id}' AND counter = '{counter}' GROUP BY resource_id",
    )
    return {str(r): int(n) for r, n in rows}


def snapshot_problem(pg: PostgresContainer, org: UUID, schedule_id: str) -> Problem:
    async def go() -> Problem:
        engine = create_async_engine(db_url(pg, *APP))
        try:
            async with scoped_transaction(engine, org) as session:
                return (await build_snapshot(session, org, UUID(schedule_id))).problem
        finally:
            await engine.dispose()

    return asyncio.run(go())


def publish_ok(client: TestClient, admin: Account, version_id: str) -> None:
    response = publish(client, admin, version_id)
    assert response.status_code == 200, response.text


def test_HC_03_publish_writes_ledger_rows(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w, a, _ = ward(client, app)
    assert snapshot_problem(migrated_pg, w.admin.organisation_id, a.schedule_id).history is None
    _, version = solve_now(client, w.admin, a.schedule_id)
    publish_ok(client, w.admin, version)

    assert ledger(migrated_pg, a.schedule_id) == night_counts(client, w.admin, version)
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT day, count, version_id FROM fairness_ledger "
        f"WHERE schedule_id = '{a.schedule_id}' AND counter = 'nights' ORDER BY day",
    )
    # One night a day; a 23:00 Kampala shift belongs to its local start date.
    assert [r[0] for r in rows] == [date(2027, 1, d) for d in range(4, 11)]
    assert {(r[1], str(r[2])) for r in rows} == {(1, version)}
    # Sat and Sun nights also count as weekends.
    assert sum(ledger(migrated_pg, a.schedule_id, "weekends").values()) == 2


def test_HC_03_history_feeds_next_schedule(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w, a, b = ward(client, app)
    _, version = solve_now(client, w.admin, a.schedule_id)
    publish_ok(client, w.admin, version)

    history = snapshot_problem(migrated_pg, w.admin.organisation_id, b.schedule_id).history
    assert history is not None
    assert history[b.nights_rule_id] == night_counts(client, w.admin, version)
    # A's own snapshot looks back from A's start: nothing before it.
    assert snapshot_problem(migrated_pg, w.admin.organisation_id, a.schedule_id).history is None


def test_HC_03_republish_replaces_ledger_rows(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w, a, _ = ward(client, app)
    _, v1 = solve_now(client, w.admin, a.schedule_id)
    publish_ok(client, w.admin, v1)
    before = night_counts(client, w.admin, v1)

    v2 = None
    for assignment in get_version(client, w.admin, v1)["assignments"]:
        holder = assignment["resources"]["nurse"][0]
        for other in (n for n in w.nurse_ids if n != holder):
            response = client.post(
                f"/api/v1/solution-versions/{v1}/drafts",
                headers=w.admin.auth,
                json={
                    "changes": [
                        {
                            "activity_id": assignment["activity_id"],
                            "start_at": assignment["start_at"],
                            "resources": {"nurse": [other]},
                        }
                    ]
                },
            )
            if response.status_code == 201:
                v2 = response.json()["id"]
                break
        if v2:
            break
    assert v2 is not None, "no valid single reassignment found"
    after = night_counts(client, w.admin, v2)
    assert after != before

    publish_ok(client, w.admin, v2)
    assert ledger(migrated_pg, a.schedule_id) == after
    [(versions,)] = fetch(
        superuser_url(migrated_pg),
        f"SELECT array_agg(DISTINCT version_id) FROM fairness_ledger "
        f"WHERE schedule_id = '{a.schedule_id}'",
    )
    assert [str(v) for v in versions] == [v2]


def test_HC_03_archive_clears_ledger_rows(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w, a, b = ward(client, app)
    _, version = solve_now(client, w.admin, a.schedule_id)
    _, draft = solve_now(client, w.admin, a.schedule_id)
    publish_ok(client, w.admin, version)

    # Archiving a draft leaves the published roster's rows alone.
    archived = client.post(f"/api/v1/solution-versions/{draft}/archive", headers=w.admin.auth)
    assert archived.status_code == 200, archived.text
    assert ledger(migrated_pg, a.schedule_id) != {}

    archived = client.post(f"/api/v1/solution-versions/{version}/archive", headers=w.admin.auth)
    assert archived.status_code == 200, archived.text
    assert ledger(migrated_pg, a.schedule_id) == {}
    assert ledger(migrated_pg, a.schedule_id, "weekends") == {}
    assert snapshot_problem(migrated_pg, w.admin.organisation_id, b.schedule_id).history is None


def test_HC_03_history_window_excludes_self_overlap_and_deleted(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w, a, b = ward(client, app)
    c, _ = roster(client, w.admin, ("2026-12-28", "2027-01-03"))
    versions: dict[str, str] = {}
    for r in (a, b, c):
        _, versions[r.schedule_id] = solve_now(client, w.admin, r.schedule_id)
        publish_ok(client, w.admin, versions[r.schedule_id])
    deleted = client.delete(f"/api/v1/schedules/{c.schedule_id}", headers=w.admin.auth)
    assert deleted.status_code == 204, deleted.text
    assert ledger(migrated_pg, c.schedule_id) != {}  # kept, but its schedule is no longer live

    org = w.admin.organisation_id
    nurse = w.nurse_ids[0]
    a_version, b_version = versions[a.schedule_id], versions[b.schedule_id]

    def row(schedule_id: str, version: str, day: str, count: int) -> str:
        return (
            "INSERT INTO fairness_ledger (organisation_id, schedule_id, version_id, resource_id, "
            f"counter, day, count) VALUES ('{org}', '{schedule_id}', '{version}', '{nurse}', "
            f"'nights', '{day}', {count})"
        )

    # Lookback is 84 days: B starts 2027-01-11, so the window opens on 2026-10-19.
    for statement in (
        row(b.schedule_id, b_version, "2027-01-01", 100),  # B itself
        row(a.schedule_id, a_version, "2027-01-11", 1000),  # on B's start
        row(a.schedule_id, a_version, "2026-10-18", 10000),  # older than the lookback
        row(a.schedule_id, a_version, "2026-10-19", 7),  # first day of the window
    ):
        execute(superuser_url(migrated_pg), statement)

    expected = night_counts(client, w.admin, a_version)
    expected[nurse] = expected.get(nurse, 0) + 7
    history = snapshot_problem(migrated_pg, org, b.schedule_id).history
    assert history is not None
    assert history[b.nights_rule_id] == expected


def test_HC_03_ledger_isolation(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    w1, a1, b1 = ward(client, app)
    _, version = solve_now(client, w1.admin, a1.schedule_id)
    publish_ok(client, w1.admin, version)
    org1 = w1.admin.organisation_id
    before = snapshot_problem(migrated_pg, org1, b1.schedule_id).history
    assert before is not None

    w2, a2, _ = ward(client, app, nurses=4)
    _, other = solve_now(client, w2.admin, a2.schedule_id)
    publish_ok(client, w2.admin, other)
    org2 = w2.admin.organisation_id

    assert snapshot_problem(migrated_pg, org1, b1.schedule_id).history == before

    async def visible(org: UUID | None) -> set[UUID]:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            async with scoped_transaction(engine, org) as session:
                return set(await session.scalars(select(FairnessLedgerRow.organisation_id)))
        finally:
            await engine.dispose()

    assert asyncio.run(visible(org2)) == {org2}
    assert asyncio.run(visible(org1)) == {org1}
    assert asyncio.run(visible(None)) == set()

    async def forge() -> None:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            async with scoped_transaction(engine, org1) as session:
                row = (await session.scalars(select(FairnessLedgerRow).limit(1))).one()
                template = (
                    row.schedule_id,
                    row.version_id,
                    row.resource_id,
                    row.day,
                )
            async with scoped_transaction(engine, org2) as session:
                session.add(
                    FairnessLedgerRow(
                        organisation_id=org1,
                        schedule_id=template[0],
                        version_id=template[1],
                        resource_id=template[2],
                        counter="forged",
                        day=template[3],
                        count=1,
                    )
                )
        finally:
            await engine.dispose()

    with pytest.raises(DBAPIError, match="row-level security"):
        asyncio.run(forge())
