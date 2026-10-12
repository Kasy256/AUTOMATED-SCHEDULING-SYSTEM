"""ISBAT Term 1 built through the product: template -> CSV imports -> term split -> snapshot.

The renamed snapshot is pinned as the engine benchmark fixture; set CARTLYF_WRITE_FIXTURES=1 to
rewrite it after an intended change to the template or the import.
"""

import asyncio
import csv
import io
import json
import os
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.industry_templates.schemas import IndustryTemplateDefinition, load_packaged
from cartlyf_api.main import create_app
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Assignment, Problem
from support import APP, Account, db_url, make_settings, signup_and_confirm

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[3] / "packages/engine/tests/fixtures/isbat/v1"
PROBLEM_FILE = FIXTURES / "term1_problem.json"
WEEK = {"start_date": "2026-01-12", "end_date": "2026-01-16", "timezone": "Africa/Kampala"}


@dataclass(frozen=True)
class Term1:
    problem: Problem  # ids renamed to codes and names
    template: IndustryTemplateDefinition


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _import(
    client: TestClient, admin: Account, job: dict[str, Any], name: str, mapping: object
) -> None:
    created = client.post("/api/v1/imports", headers=admin.auth, json=job | {"filename": name})
    url = f"/api/v1/imports/{created.json()['id']}"
    client.put(
        f"{url}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=_read(name).encode(),
    )
    dry = client.post(f"{url}/dry-run", headers=admin.auth, json={"mapping": mapping})
    assert dry.status_code == 200 and dry.json()["report"]["valid"], dry.text
    assert client.post(f"{url}/commit", headers=admin.auth).status_code == 200


def _resources(
    client: TestClient, admin: Account, type_id: UUID | str, name: str, **fields: object
) -> None:
    mapping = {"kind": "resources", "code": "code", "name": "name"} | fields
    _import(client, admin, {"kind": "resources", "resource_type_id": str(type_id)}, name, mapping)


def _demand_mapping(
    template: IndustryTemplateDefinition, applied: dict[str, Any]
) -> dict[str, Any]:
    shape = template.demand_shape
    assert shape is not None and shape.term_split is not None
    types = applied["resource_type_ids"]
    return {
        "kind": "demands",
        "demand_kind": shape.kind,
        "slot_template_id": applied["slot_template_ids"][shape.slot_template],
        "name": shape.name_column,
        "sessions_per_week": shape.sessions_per_week_column,
        "weekly_minutes": shape.weekly_minutes_column,
        "requirements": [
            {
                "role": r.role,
                "resource_type_id": types[r.resource_type_key],
                "count_min": r.count_min,
                "count_max": r.count_max,
                "count_from_fixed": r.count_from_fixed,
                "fixed_codes_column": r.fixed_codes_column,
                "tags_column": r.tags_column,
                "attribute_columns": r.attribute_columns,
            }
            for r in shape.requirements
        ],
        "term_split": shape.term_split.model_dump() | {"term": "Term 1"},
    }


def _hhmm(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def _snapshot(pg: PostgresContainer, admin: Account, schedule_id: str) -> Problem:
    async def run() -> Problem:
        engine = create_async_engine(db_url(pg, *APP))
        try:
            async with scoped_transaction(engine, admin.organisation_id) as session:
                snap = await build_snapshot(session, admin.organisation_id, UUID(schedule_id))
                return snap.problem
        finally:
            await engine.dispose()

    return asyncio.run(run())


_ID_LISTS = {"fixed_resource_ids", "resource_ids", "series_ids"}


def _resorted(value: object) -> object:
    # The snapshot sorts id lists by uuid; after renaming they are re-sorted by name.
    if isinstance(value, dict):
        items = cast(dict[str, object], value).items()
        return {
            k: sorted(cast(list[str], v))
            if k in _ID_LISTS and isinstance(v, list)
            else _resorted(v)
            for k, v in items
        }
    if isinstance(value, list):
        return [_resorted(v) for v in cast(list[object], value)]
    return value


def _renamed(problem: Problem, names: dict[str, str]) -> Problem:
    text = problem.model_dump_json()
    for uid, name in names.items():
        text = text.replace(uid, name)
    data = cast(dict[str, Any], _resorted(json.loads(text)))
    for key in ("resources", "activities", "constraints"):
        data[key] = sorted(data[key], key=lambda item: item["id"])
    return Problem.model_validate(data)


def _canonical(problem: Problem) -> str:
    return json.dumps(problem.model_dump(mode="json"), indent=1, sort_keys=True) + "\n"


def _build(client: TestClient, pg: PostgresContainer) -> Problem:
    admin = signup_and_confirm(client, client.app)  # type: ignore[arg-type]
    template = load_packaged("education")
    applied = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={"template_key": "education", "name": "ISBAT Term 1"} | WEEK,
    ).json()
    types = applied["resource_type_ids"]
    _resources(
        client,
        admin,
        types["lecturer"],
        "lecturers.csv",
        tags="subjects",
        attributes={"role": "role", "faculty": "faculty"},
    )
    _resources(
        client,
        admin,
        types["room"],
        "rooms.csv",
        capacity="capacity",
        tags="specialisations",
        attributes={"room_type": "room_type"},
    )
    _resources(
        client,
        admin,
        types["student_group"],
        "student_groups.csv",
        size="size",
        attributes={"program": "program", "semester": "semester"},
    )
    resources = client.get("/api/v1/resources", headers=admin.auth).json()
    by_code = {r["code"]: r["id"] for r in resources}
    for rule in csv.DictReader(io.StringIO(_read("lecturer_availability.csv"))):
        response = client.post(
            f"/api/v1/resources/{by_code[rule['code']]}/availability-rules",
            headers=admin.auth,
            json={
                "kind": "available",
                "weekday": int(rule["weekday"]),
                "start_minute": _hhmm(rule["start"]),
                "end_minute": _hhmm(rule["end"]),
            },
        )
        assert response.status_code == 201, response.text
    schedule_id = applied["schedule"]["id"]
    _import(
        client,
        admin,
        {"kind": "demands", "schedule_id": schedule_id},
        "course_units.csv",
        _demand_mapping(template, applied),
    )

    base = f"/api/v1/schedules/{schedule_id}"
    demands = client.get(f"{base}/demands", headers=admin.auth).json()
    activities = client.get(f"{base}/activities", headers=admin.auth).json()
    constraints = client.get(f"{base}/constraints", headers=admin.auth).json()
    names = {r["id"]: r["code"] for r in resources}
    names |= {d["id"]: d["name"] for d in demands}
    names |= {a["id"]: a["name"] for a in activities}
    names |= {c["id"]: c["name"] for c in constraints}
    assert len(set(names.values())) == len(names), "renaming would merge two ids"
    return _renamed(_snapshot(pg, admin, schedule_id), names)


@pytest.fixture(scope="module")
def term1(
    migrated_pg: PostgresContainer,
    redis_container: RedisContainer,
    minio_settings: dict[str, object],
) -> Iterator[Term1]:
    redis_container.get_client().flushdb()  # pyright: ignore[reportUnknownMemberType]
    host = redis_container.get_container_host_ip()
    redis_url = f"redis://{host}:{redis_container.get_exposed_port(redis_container.port)}/0"
    app = create_app(make_settings(db_url(migrated_pg, *APP), redis_url, **minio_settings))
    with TestClient(app, raise_server_exceptions=False) as client:
        problem = _build(client, migrated_pg)
    if os.environ.get("CARTLYF_WRITE_FIXTURES") == "1":
        PROBLEM_FILE.write_text(_canonical(problem), encoding="utf-8", newline="\n")
    yield Term1(problem, load_packaged("education"))


def test_EDU_term1_shape(term1: Term1) -> None:
    problem = term1.problem
    assert len({a.series_id for a in problem.activities}) == 17
    assert len(problem.activities) == 34
    assert all(len(a.candidate_starts) == 20 for a in problem.activities)
    part_timers = {r.id for r in problem.resources if r.attrs.get("role") == "Part-Time"}
    assert part_timers == {"L003", "L014"}
    assert all(r.unavailable for r in problem.resources if r.id in part_timers)


def test_EDU_02_constraints_come_only_from_the_template(term1: Term1) -> None:
    def shape(key: str, params: object, hard: bool, weight: int) -> str:
        return json.dumps([key, params, hard, weight], sort_keys=True)

    ours = Counter(
        shape(c.template_key, c.params, c.hard, c.weight) for c in term1.problem.constraints
    )
    template = Counter(
        shape(c.template_key, c.params, c.hard, c.weight) for c in term1.template.constraints
    )
    assert ours == template
    lecturer_rules = [c for c in term1.problem.constraints if c.scope.resource_type_keys]
    assert all(
        set(c.scope.resource_type_keys) <= {"lecturer", "student_group"} for c in lecturer_rules
    )


def test_EDU_04_merged_subject_is_one_series_with_all_groups(term1: Term1) -> None:
    problem = term1.problem
    prog_c = [a for a in problem.activities if a.series_id == "PROG_C"]
    assert len(prog_c) == 2
    for activity in prog_c:
        roles = {r.role: r for r in activity.requirements}
        assert set(roles["group"].fixed_resource_ids) == {"SG_BSCAIT_126_S1", "SG_BCS_126_S1"}
        assert (roles["group"].count_min, roles["group"].count_max) == (2, 2)
        assert [(p.attr, p.value) for p in roles["room"].filter.attrs] == [("room_type", "Lab")]
        assert roles["lecturer"].filter.tags == ("PROG_C",)

    # Summed headcount (32 + 40) is what capacity_fit checks: a 70-seat lab is too small.
    small_lab = next(
        r
        for r in problem.resources
        if r.attrs.get("room_type") == "Lab" and r.capacity and 32 < r.capacity < 72
    )
    activity = prog_c[0]
    assignment = Assignment(
        activity_id=activity.id,
        start=activity.candidate_starts[0],
        resources={
            "group": tuple(
                sorted(
                    next(r for r in activity.requirements if r.role == "group").fixed_resource_ids
                )
            ),
            "lecturer": tuple(r.id for r in problem.resources if "PROG_C" in r.tags)[:1],
            "room": (small_lab.id,),
        },
    )
    score = check(problem, [assignment])
    assert any(v.constraint_id == "Room seats every student" for v in score.violations)


def test_EDU_fixture_is_current(term1: Term1) -> None:
    assert PROBLEM_FILE.exists(), "run once with CARTLYF_WRITE_FIXTURES=1"
    assert PROBLEM_FILE.read_text(encoding="utf-8") == _canonical(term1.problem), (
        "term1_problem.json is stale: rerun with CARTLYF_WRITE_FIXTURES=1"
    )
