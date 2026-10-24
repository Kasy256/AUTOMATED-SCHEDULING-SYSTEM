from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope
from kit import DAY, act, needs, person, place, problem, rule, solved, start_of
from strategies import agreement, tiny_problems


def _day(per: int = 30, weight: int = 1, scope: Scope | None = None) -> Problem:
    return problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, 180, DAY], needs())],
        [rule("gaps", "minimize_gaps", hard=False, weight=weight, per_minutes=per, scope=scope)],
    )


def test_RUL_minimize_gaps_01_solver_closes_gaps() -> None:
    solution = solved(_day())
    assert solution.stats.objective == 0
    assert start_of(solution, "a2") in (60, DAY)


def test_RUL_minimize_gaps_02_and_03_formula_and_text() -> None:
    score = check(_day(per=50, weight=2), [place("a1", 0, who="p"), place("a2", 180, who="p")])
    assert score.soft_total == 2 * (120 // 50)
    assert score.terms[0].details == (
        "Keep idle time between a resource's activities short (per 50 minutes): "
        "p is idle 120 minutes on day 1"
    )


def test_RUL_minimize_gaps_03_days_are_separate() -> None:
    assert check(_day(), [place("a1", 0, who="p"), place("a2", DAY, who="p")]).soft_total == 0


def test_RUL_minimize_gaps_05_scope() -> None:
    p = _day(scope=Scope(resource_ids=("q",)))
    assert check(p, [place("a1", 0, who="p"), place("a2", 180, who="p")]).soft_total == 0


@agreement
@given(tiny_problems(keys=("minimize_gaps",)))
def test_RUL_minimize_gaps_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
