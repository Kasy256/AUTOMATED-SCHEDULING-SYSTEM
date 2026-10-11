from cartlyf_engine.domain import AttributePredicate, Scope
from cartlyf_engine.index import ProblemIndex, window_index
from cartlyf_engine.templates.scope import in_scope, scoped_activities, series_of
from cartlyf_engine.templates.text import count
from kit import DAY, act, group, needs, person, problem, room, win


def test_window_index_is_half_open() -> None:
    windows = (win(0, 10), win(10, 20))
    assert [window_index(windows, m) for m in (0, 9, 10, 19, 20)] == [0, 0, 1, 1, None]


def test_eligibility_and_candidates_follow_requirement_filters() -> None:
    p = problem(
        [person("p", "x"), person("q"), room("r", 30)],
        [act("a1", 60, [0], needs("who", "person", "x"), needs("room", "room"))],
    )
    index = ProblemIndex(p)
    assert index.eligible("a1", "who") == ("p",)
    assert index.eligible("a1", "room") == ("r",)
    assert index.candidates("a1") == frozenset({"p", "r"})


def test_attribute_uses_start_period_and_named_window() -> None:
    index = ProblemIndex(problem([], [act("a1", 60, [0], series="s1")]))
    assert index.attribute(DAY + 60, "day", None) == 1
    assert index.attribute(DAY + 60, "week", None) == 0
    assert index.attribute(DAY + 60, "horizon", None) == 0
    assert index.attribute(DAY + 60, "day", "morning") == 1
    assert index.attribute(DAY + 800, "day", "morning") is None


def test_scope_fields_all_must_hold() -> None:
    p = person("p", "x", "y", attrs={"grade": 2})
    assert in_scope(p, Scope())
    assert in_scope(p, Scope(resource_type_keys=("room", "person"), tags=("x",)))
    assert not in_scope(p, Scope(tags=("x", "z")))
    assert not in_scope(p, Scope(resource_ids=("q",)))
    assert in_scope(p, Scope(attrs=(AttributePredicate(attr="grade", op="gte", value=2),)))
    assert not in_scope(group("g", 10), Scope(resource_type_keys=("person",)))


def test_series_scope_and_grouping_keep_problem_order() -> None:
    p = problem(
        [],
        [
            act("a1", 60, [0], series="s1"),
            act("a2", 60, [0], series="s2"),
            act("a3", 60, [0], series="s1"),
            act("a4", 60, [0]),
        ],
    )
    assert [a.id for a in scoped_activities(p, Scope(series_ids=("s1",)))] == ["a1", "a3"]
    grouped = series_of(list(p.activities))
    assert {k: [a.id for a in v] for k, v in grouped.items()} == {"s1": ["a1", "a3"], "s2": ["a2"]}


def test_count_pluralises() -> None:
    assert count(1, "activity", "activities") == "1 activity"
    assert count(2, "activity", "activities") == "2 activities"
