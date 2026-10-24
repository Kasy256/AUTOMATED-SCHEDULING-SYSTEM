import pytest
from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, Window
from cartlyf_engine.templates.registry import InvalidInstance, validate_instance
from kit import act, needs, person, place, problem, rule, solved, start_of, who, win
from strategies import agreement, tiny_problems

TEXT = "Stay close to the published plan (1 per moved activity, 1 per replaced resource)"


def _repair(
    *,
    weight: int = 1,
    per_change: int = 1,
    per_resource_change: int = 1,
    scope: Scope | None = None,
    unavailable: tuple[Window, ...] = (),
) -> Problem:
    return problem(
        [person("p", unavailable=unavailable), person("q")],
        [
            act("a1", 60, [0, 120], needs(), series="s1"),
            act("a2", 60, [0, 120], needs(), series="s2"),
        ],
        [
            rule(
                "stay",
                "stability",
                hard=False,
                weight=weight,
                per_change=per_change,
                per_resource_change=per_resource_change,
                scope=scope,
            )
        ],
        baseline=[place("a1", 120, who="p"), place("a2", 120, who="q")],
    )


def test_RUL_stability_01_solver_keeps_the_baseline() -> None:
    solution = solved(_repair())
    assert sorted(solution.assignments, key=lambda a: a.activity_id) == [
        place("a1", 120, who="p"),
        place("a2", 120, who="q"),
    ]
    assert solution.score.soft_total == 0


def test_RUL_stability_01_changes_only_what_it_must() -> None:
    solution = solved(_repair(per_resource_change=5, unavailable=(win(120, 180),)))
    assert (start_of(solution, "a1"), who(solution, "a1")) == (0, ("p",))
    assert (start_of(solution, "a2"), who(solution, "a2")) == (120, ("q",))
    assert solution.score.soft_total == 1


def test_RUL_stability_01_cannot_be_hard() -> None:
    with pytest.raises(InvalidInstance, match="can only be soft"):
        validate_instance(
            "stability", 1, {"per_change": 1, "per_resource_change": 1}, hard=True, weight=0
        )


def test_RUL_stability_02_checker_names_each_change() -> None:
    score = check(_repair(), [place("a1", 0, who="q"), place("a2", 120, who="q")])
    (term,) = score.terms
    assert term.details == f"{TEXT}: a1 moved from minute 120 to 0 and no longer has p"


def test_RUL_stability_03_penalty_formula() -> None:
    p = _repair(weight=2, per_change=3, per_resource_change=5)
    moved_and_replaced = [place("a1", 0, who="q"), place("a2", 120, who="q")]
    assert check(p, moved_and_replaced).soft_total == 2 * (3 + 5)
    no_baseline = p.model_copy(update={"baseline": None})
    assert check(no_baseline, moved_and_replaced).soft_total == 0


def test_RUL_stability_03_ignores_vanished_activities_and_resources() -> None:
    p = _repair().model_copy(
        update={
            "baseline": (
                place("a1", 120, who=("p", "gone")),
                place("a2", 120, who="q"),
                place("vanished", 0, who="p"),
            )
        }
    )
    assert check(p, [place("a1", 120, who="p"), place("a2", 120, who="q")]).soft_total == 0


def test_RUL_stability_05_scope_series() -> None:
    p = _repair(scope=Scope(series_ids=("s2",)))
    assert check(p, [place("a1", 0, who="q"), place("a2", 120, who="q")]).soft_total == 0
    assert check(p, [place("a1", 120, who="p"), place("a2", 0, who="q")]).soft_total == 1


def test_RUL_stability_05_scope_resources() -> None:
    p = _repair(scope=Scope(resource_ids=("q",)))
    # a1 loses p (out of scope): free. a2 moves (1) and loses q (1).
    assert check(p, [place("a1", 120, who="q"), place("a2", 0, who="p")]).soft_total == 2


@agreement
@given(tiny_problems(keys=("stability",)))
def test_RUL_stability_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
