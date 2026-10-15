import pytest

from cartlyf_engine.domain import CORE_RULES, CORE_UNAVAILABLE
from cartlyf_engine.explain import explain_assignment
from kit import DAY, act, needs, person, place, problem, rule, solved, win


def test_EXP_01_names_the_rule_that_keeps_it_here() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, DAY], needs())],
        [rule("daily", "max_load", period="day", max_count=1)],
    )
    why = explain_assignment(p, solved(p).assignments, "a2")
    assert [(b.constraint_id, b.rule, b.hard, b.blocks) for b in why.binding] == [
        ("daily", "At most 1 activity per day", True, 1)
    ]
    (alternative,) = why.alternatives
    assert alternative.start == 60
    assert not alternative.check.valid


def test_EXP_01_resource_alternatives_and_core_rules() -> None:
    p = problem([person("p"), person("q", unavailable=[win(0, 60)])], [act("a1", 60, [0], needs())])
    why = explain_assignment(p, [place("a1", 0, who="p")], "a1")
    assert [(b.constraint_id, b.rule, b.hard, b.blocks) for b in why.binding] == [
        (CORE_UNAVAILABLE, CORE_RULES[CORE_UNAVAILABLE], True, 1)
    ]
    assert [a.resources for a in why.alternatives] == [{"who": ("q",)}]


def test_EXP_01_soft_rules_are_listed_after_hard_ones() -> None:
    p = problem(
        [person("p", avoided=[win(60, 120)])],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, DAY], needs())],
        [
            rule("daily", "max_load", period="day", max_count=1),
            rule("pref", "preference", hard=False, weight=1, source="calendar"),
        ],
    )
    why = explain_assignment(p, [place("a1", 0, who="p"), place("a2", DAY, who="p")], "a2")
    assert [(b.constraint_id, b.hard, b.blocks, b.penalises) for b in why.binding] == [
        ("daily", True, 1, 0),
        ("pref", False, 0, 1),
    ]


def test_EXP_01_unplaced_activity_is_an_error() -> None:
    p = problem([person("p")], [act("a1", 60, [0], needs())])
    with pytest.raises(ValueError, match="not placed"):
        explain_assignment(p, [], "a1")
