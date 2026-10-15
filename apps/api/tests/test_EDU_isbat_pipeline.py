"""ISBAT Term 1 built through the product: template -> CSV imports -> term split -> snapshot.

The renamed snapshot is pinned as the engine benchmark fixture; set CARTLYF_WRITE_FIXTURES=1 to
rewrite it after an intended change to the template or the import.
"""

import asyncio
import json
import os
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from isbat import FIXTURES, build_term1
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.industry_templates.schemas import IndustryTemplateDefinition, load_packaged
from cartlyf_api.main import create_app
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Assignment, Problem
from support import APP, Account, db_url, make_settings

pytestmark = pytest.mark.integration

PROBLEM_FILE = FIXTURES / "term1_problem.json"


@dataclass(frozen=True)
class Term1:
    problem: Problem  # ids renamed to codes and names
    template: IndustryTemplateDefinition


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
    built = build_term1(client)
    return _renamed(_snapshot(pg, built.admin, built.schedule_id), built.names)


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
