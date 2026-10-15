from cartlyf_engine.checker import check
from cartlyf_engine.domain import Pin
from cartlyf_engine.index import ProblemIndex
from kit import DAY, act, messages, needs, person, place, problem, room, win


def test_valid_assignment_scores_zero() -> None:
    p = problem([person("p")], [act("a1", 60, [0, 60], needs())])
    score = check(p, [place("a1", 60, who="p")])
    assert (score.hard_violations, score.soft_total, score.terms, score.violations) == (
        0,
        0,
        (),
        (),
    )


def test_placement_errors_are_violations_not_exceptions() -> None:
    p = problem([person("p")], [act("a1", 60, [0], needs()), act("a2", 60, [0], needs())])
    score = check(
        p,
        [place("zz", 0, who="p"), place("a1", 30, who="p")],
    )
    assert [(v.constraint_id, v.message) for v in score.violations] == [
        ("core:placement", "Unknown activity zz"),
        ("core:placement", "a1 starts at 30, which is not a candidate start"),
        ("core:placement", "a2 is not placed"),
    ]
    assert messages(p, place("a1", 0, who="p"), place("a1", 0, who="p"), place("a2", 0, who="p"))[
        0
    ] == ("a1 is placed more than once")


def test_requirement_errors() -> None:
    p = problem(
        [person("p", "x"), person("q"), room("r", 10)],
        [act("a1", 60, [0], needs("who", "person", "x", fixed=["p"]))],
    )
    assert messages(p, place("a1", 0, who=["q"], extra="p")) == [
        "q does not match role 'who' of a1",
        "a1 has no role 'extra'",
        "p is fixed on role 'who' of a1 but not assigned",
    ]
    assert messages(p, place("a1", 0, who=["p", "ghost"])) == [
        "a1 names unknown resource ghost",
        "Role 'who' of a1 has 2 resources, at most 1 allowed",
    ]
    assert messages(p, place("a1", 0)) == [
        "Role 'who' of a1 has 0 resources, needs 1",
        "p is fixed on role 'who' of a1 but not assigned",
    ]
    q = problem(
        [person("p")], [act("a1", 60, [0], needs("who", count=1, count_max=2), needs("also"))]
    )
    assert messages(q, place("a1", 0, who="p", also="p")) == ["p fills more than one place in a1"]


def test_soft_requirement_shortfall_is_one_term() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs(count=3, hard=False, weight=4)), act("a2", 60, [100], needs())],
    )
    score = check(p, [place("a1", 0, who="p"), place("a2", 100, who="p")])
    assert score.hard_violations == 0
    assert [(t.constraint_id, t.penalty, t.details) for t in score.terms] == [
        ("core:requirements", 8, "Role 'who' of a1 is short by 2")
    ]
    assert score.soft_total == 8


def test_overlap_beyond_concurrency() -> None:
    p = problem(
        [person("p"), person("c", concurrency=2)],
        [act(f"a{i}", 60, [0, 30], needs("who", None)) for i in range(1, 4)],
    )
    assert messages(
        p, place("a1", 0, who="p"), place("a2", 30, who="p"), place("a3", 0, who="c")
    ) == ["p is in 2 activities at minute 30, limit 1"]
    assert messages(
        p, place("a1", 0, who="c"), place("a2", 30, who="c"), place("a3", 0, who="c")
    ) == ["c is in 3 activities at minute 30, limit 2"]


def test_unavailable_and_pins() -> None:
    p = problem(
        [person("p", unavailable=[win(0, 30), win(DAY, DAY + 60)])],
        [act("a1", 60, [0, 60], needs(), pin=Pin(start=60, resources={"who": ("p",)}))],
    )
    assert messages(p, place("a1", 0)) == [
        "Role 'who' of a1 has 0 resources, needs 1",
        "a1 is pinned to start 60 but starts at 0",
        "a1 is pinned to p in role 'who'",
    ]
    assert messages(p, place("a1", 0, who="p")) == [
        "p is unavailable during a1 (minutes 0-30)",
        "a1 is pinned to start 60 but starts at 0",
    ]
    assert check(p, [place("a1", 60, who="p")]).hard_violations == 0


def test_a_wider_problems_index_gives_the_same_score() -> None:
    whole = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs()), act("a2", 60, [0], needs())],
    )
    part = whole.model_copy(update={"activities": whole.activities[:1]})
    placed = [place("a1", 0, who="p")]
    assert check(part, placed, index=ProblemIndex(whole)) == check(part, placed)
