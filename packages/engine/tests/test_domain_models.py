import pytest
from pydantic import ValidationError

from cartlyf_engine.domain import (
    Activity,
    ActivityFilter,
    AttributePredicate,
    Pin,
    Problem,
    Requirement,
    Resource,
    ResourceFilter,
    Window,
    activity_matches,
    predicate_holds,
    resource_matches,
)


def lecturer(**overrides: object) -> Resource:
    data: dict[str, object] = {
        "id": "r1",
        "type_key": "lecturer",
        "kind": "person",
        "tags": ["math101"],
        "attrs": {"role": "full_time", "max_hours": 22, "langs": ["en", "fr"]},
    }
    return Resource.model_validate(data | overrides)


def activity(**overrides: object) -> Activity:
    data: dict[str, object] = {
        "id": "a1",
        "duration": 60,
        "candidate_starts": [0, 120],
        "requirements": [{"role": "lecturer", "count_min": 1, "count_max": 1}],
    }
    return Activity.model_validate(data | overrides)


def test_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        lecturer().id = "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        lecturer(colour="red")


def test_window_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="after start"):
        Window(start=10, end=10)


@pytest.mark.parametrize(
    ("predicate", "expected"),
    [
        ({"attr": "role", "op": "eq", "value": "full_time"}, True),
        ({"attr": "role", "op": "ne", "value": "full_time"}, False),
        ({"attr": "role", "op": "in", "value": ["dean", "full_time"]}, True),
        ({"attr": "max_hours", "op": "gte", "value": 22}, True),
        ({"attr": "max_hours", "op": "lte", "value": 21.5}, False),
        ({"attr": "langs", "op": "contains", "value": "fr"}, True),
        ({"attr": "missing", "op": "ne", "value": "x"}, False),
        ({"attr": "max_hours", "op": "eq", "value": True}, False),
    ],
)
def test_predicates(predicate: dict[str, object], expected: bool) -> None:
    parsed = AttributePredicate.model_validate(predicate)
    assert predicate_holds(lecturer().attrs, parsed) is expected


@pytest.mark.parametrize(
    "predicate",
    [
        {"attr": "role", "op": "in", "value": "dean"},
        {"attr": "role", "op": "eq", "value": ["a"]},
        {"attr": "role", "op": "gte", "value": "x"},
        {"attr": "role", "op": "contains", "value": 3},
    ],
)
def test_predicate_value_must_fit_operator(predicate: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AttributePredicate.model_validate(predicate)


def test_resource_filter_matches_type_tags_and_attrs() -> None:
    resource = lecturer()
    assert resource_matches(resource, ResourceFilter())
    assert resource_matches(resource, ResourceFilter(type_key="lecturer", tags=("math101",)))
    assert not resource_matches(resource, ResourceFilter(type_key="room"))
    assert not resource_matches(resource, ResourceFilter(tags=("math101", "phy201")))
    role_is_dean = AttributePredicate(attr="role", op="eq", value="dean")
    assert not resource_matches(resource, ResourceFilter(attrs=(role_is_dean,)))


def test_activity_filter() -> None:
    a = activity(series_id="s1", attrs={"shift": "night"})
    night = AttributePredicate(attr="shift", op="eq", value="night")
    assert activity_matches(a, ActivityFilter(series_ids=("s1",), attrs=(night,)))
    assert not activity_matches(a, ActivityFilter(series_ids=("s2",)))


def test_requirement_counts_and_soft_weight() -> None:
    with pytest.raises(ValidationError, match="count_max"):
        Requirement(role="room", count_min=2, count_max=1)
    with pytest.raises(ValidationError, match="weight"):
        Requirement(role="nurse", count_min=3, count_max=3, hard=False)
    with pytest.raises(ValidationError, match="fixed"):
        Requirement(role="group", count_min=1, count_max=1, fixed_resource_ids=("g1", "g2"))
    soft = Requirement(role="nurse", count_min=3, count_max=3, hard=False, weight=100)
    assert soft.filter == ResourceFilter()


def test_activity_validation() -> None:
    with pytest.raises(ValidationError, match="increasing"):
        activity(candidate_starts=[120, 0])
    with pytest.raises(ValidationError):
        activity(candidate_starts=[])
    with pytest.raises(ValidationError, match="roles"):
        activity(
            requirements=[
                {"role": "room", "count_min": 1, "count_max": 1},
                {"role": "room", "count_min": 1, "count_max": 1},
            ]
        )
    with pytest.raises(ValidationError, match="candidate"):
        activity(pinned={"start": 60})
    with pytest.raises(ValidationError, match="role"):
        activity(pinned={"resources": {"room": ["x"]}})
    with pytest.raises(ValidationError, match="start or resources"):
        Pin()


def problem_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "horizon_minutes": 1440,
        "day_windows": [{"start": 0, "end": 1440}],
        "week_windows": [{"start": 0, "end": 1440}],
        "resources": [lecturer().model_dump()],
        "activities": [activity().model_dump()],
    }
    return data | overrides


def test_problem_accepts_a_consistent_snapshot() -> None:
    problem = Problem.model_validate(problem_data())
    assert problem.options.num_workers >= 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"resources": [lecturer().model_dump(), lecturer().model_dump()]}, "duplicate resource"),
        ({"activities": [activity(candidate_starts=[1400]).model_dump()]}, "horizon"),
        ({"day_windows": [{"start": 0, "end": 2000}]}, "horizon"),
        (
            {
                "activities": [
                    activity(
                        requirements=[
                            {
                                "role": "g",
                                "count_min": 1,
                                "count_max": 1,
                                "fixed_resource_ids": ["nope"],
                            }
                        ]
                    ).model_dump()
                ]
            },
            "unknown resource",
        ),
    ],
)
def test_problem_rejects_inconsistent_snapshots(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Problem.model_validate(problem_data(**overrides))
