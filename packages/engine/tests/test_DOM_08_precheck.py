from cartlyf_engine.domain import Problem
from cartlyf_engine.precheck import available_minutes, precheck

DAY = 1440


def problem(resources: list[dict[str, object]], activities: list[dict[str, object]]) -> Problem:
    return Problem.model_validate(
        {
            "horizon_minutes": DAY,
            "day_windows": [{"start": 0, "end": DAY}],
            "week_windows": [{"start": 0, "end": DAY}],
            "resources": resources,
            "activities": activities,
        }
    )


def room(rid: str, **extra: object) -> dict[str, object]:
    return {"id": rid, "type_key": "room", "kind": "space", "capacity": 30} | extra


def needs(aid: str, role: str, duration: int = 60, **req: object) -> dict[str, object]:
    requirement = {"role": role, "count_min": 1, "count_max": 1} | req
    return {"id": aid, "duration": duration, "candidate_starts": [0], "requirements": [requirement]}


def test_DOM_08_clean_problem_has_no_issues() -> None:
    p = problem([room("r1")], [needs("a1", "room", filter={"type_key": "room"})])
    assert precheck(p) == []


def test_DOM_08_requirement_with_zero_matching_resources() -> None:
    p = problem([room("r1")], [needs("a1", "lab", filter={"type_key": "lab"})])
    [issue] = precheck(p)
    assert issue.code == "unfillable_requirement"
    assert issue.activity_ids == ("a1",)
    assert "lab" in issue.message and "0" in issue.message


def test_DOM_08_soft_requirement_is_not_flagged() -> None:
    p = problem(
        [room("r1")], [needs("a1", "lab", filter={"type_key": "lab"}, hard=False, weight=5)]
    )
    assert precheck(p) == []


def test_DOM_08_demand_minutes_exceed_available_minutes() -> None:
    busy = room("r1", unavailable=[{"start": 0, "end": 1400}])
    activities = [
        needs(f"a{i}", "room", duration=30, filter={"type_key": "room"}) for i in range(2)
    ]
    [issue] = precheck(problem([busy], activities))
    assert issue.code == "insufficient_capacity"
    assert issue.activity_ids == ("a0", "a1")
    assert issue.resource_ids == ("r1",)
    assert "60" in issue.message and "40" in issue.message


def test_DOM_08_concurrency_multiplies_supply() -> None:
    shared = room("r1", unavailable=[{"start": 0, "end": 1400}], concurrency=2)
    activities = [
        needs(f"a{i}", "room", duration=40, filter={"type_key": "room"}) for i in range(2)
    ]
    assert precheck(problem([shared], activities)) == []


def test_DOM_08_fixed_resource_overloaded_and_mismatched() -> None:
    group: dict[str, object] = {"id": "g1", "type_key": "group", "kind": "group", "size": 40,
             "unavailable": [{"start": 60, "end": DAY}]}  # fmt: skip
    activities = [
        needs("a1", "group", duration=60, fixed_resource_ids=["g1"]),
        needs("a2", "group", duration=60, fixed_resource_ids=["g1"]),
        needs("a3", "room", fixed_resource_ids=["g1"], filter={"type_key": "room"}),
    ]
    codes = [(i.code, i.resource_ids) for i in precheck(problem([group, room("r1")], activities))]
    assert ("fixed_resource_mismatch", ("g1",)) in codes
    assert ("overloaded_resource", ("g1",)) in codes


def test_available_minutes_merges_overlaps() -> None:
    p = problem([room("r1", unavailable=[{"start": 0, "end": 100}, {"start": 50, "end": 200}])], [])
    assert available_minutes(p.resources[0], DAY) == DAY - 200
