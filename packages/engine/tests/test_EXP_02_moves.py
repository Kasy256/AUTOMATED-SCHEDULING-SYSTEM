import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cartlyf_engine.checker import check
from cartlyf_engine.domain import CORE_OVERLAP, CORE_PIN, CORE_RULES, Assignment, Pin, Problem
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.moves import MoveCheck, MoveChecker
from kit import DAY, SOLVED, act, needs, person, place, problem, rule, solve1
from strategies import agreement, tiny_problems

ALL = (
    "capacity_fit",
    "max_load",
    "min_load",
    "min_rest",
    "max_consecutive",
    "spread",
    "same_time",
    "precedence",
    "preference",
    "minimize_gaps",
    "balance",
    "day_distribution",
    "stability",
)


def _day() -> Problem:
    return problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs()), act("a2", 60, [0, 60, DAY], needs())],
        [rule("daily", "max_load", period="day", max_count=1)],
    )


NOW = [place("a1", 0, who="p"), place("a2", DAY, who="p")]


def test_EXP_02_lists_every_rule_a_move_breaks() -> None:
    report = MoveChecker(_day(), NOW).check(place("a2", 0, who="p"))
    assert not report.valid
    assert {(b.constraint_id, b.rule) for b in report.broken} == {
        (CORE_OVERLAP, CORE_RULES[CORE_OVERLAP]),
        ("daily", "At most 1 activity per day"),
    }


def test_EXP_02_names_the_breach() -> None:
    report = MoveChecker(_day(), NOW).check(place("a2", 60, who="p"))
    assert [(b.constraint_id, b.message) for b in report.broken] == [
        ("daily", "At most 1 activity per day: p has 2 activities in day 1")
    ]


def test_EXP_02_a_harmless_move_is_valid() -> None:
    assert MoveChecker(_day(), NOW).check(place("a2", 60, who="q")) == MoveCheck(valid=True)


def test_EXP_02_soft_rules_report_penalty_changes() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, 180], needs())],
        [rule("gaps", "minimize_gaps", hard=False, weight=1, per_minutes=60)],
    )
    report = MoveChecker(p, [place("a1", 0, who="p"), place("a2", 60, who="p")]).check(
        place("a2", 180, who="p")
    )
    assert report.valid
    (change,) = report.penalties
    assert (change.constraint_id, change.before) == ("gaps", 0)
    assert change.after > 0
    assert change.rule == "Keep idle time between a resource's activities short (per 60 minutes)"


def test_EXP_02_moving_a_pinned_activity_breaks_the_pin() -> None:
    p = problem([person("p")], [act("a1", 60, [0, 60], needs(), pin=Pin(start=0))])
    report = MoveChecker(p, [place("a1", 0, who="p")]).check(place("a1", 60, who="p"))
    assert [b.constraint_id for b in report.broken] == [CORE_PIN]


def test_EXP_02_unknown_activity_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown activity"):
        MoveChecker(_day(), NOW).check(place("nope", 0, who="p"))


@st.composite
def _moves(draw: st.DrawFn, p: Problem) -> Assignment:
    activity = draw(st.sampled_from(p.activities))
    index = ProblemIndex(p)
    resources: dict[str, tuple[str, ...]] = {}
    for req in activity.requirements:
        eligible = index.eligible(activity.id, req.role)
        resources[req.role] = (
            tuple(draw(st.lists(st.sampled_from(eligible), unique=True, max_size=req.count_max)))
            if eligible
            else ()
        )
    return Assignment(
        activity_id=activity.id,
        start=draw(st.sampled_from(activity.candidate_starts)),
        resources=resources,
    )


@agreement
@given(st.data(), tiny_problems(keys=ALL, max_rules=2))
def test_EXP_02_neighbourhood_matches_the_whole_schedule(data: st.DataObject, p: Problem) -> None:
    solution = solve1(p)
    assume(solution.status in SOLVED)
    move = data.draw(_moves(p))
    report = MoveChecker(p, solution.assignments).check(move)

    before = check(p, solution.assignments)
    after = check(
        p, [move if a.activity_id == move.activity_id else a for a in solution.assignments]
    )
    old = set(before.violations)
    expected = sorted((v.constraint_id, v.message) for v in after.violations if v not in old)
    assert sorted((b.constraint_id, b.message) for b in report.broken) == expected

    penalty = {t.constraint_id: t.penalty for t in before.terms}
    full = {t.constraint_id: t.penalty - penalty[t.constraint_id] for t in after.terms}
    local = {c.constraint_id: c.after - c.before for c in report.penalties}
    assert local == {k: v for k, v in full.items() if v != 0}
