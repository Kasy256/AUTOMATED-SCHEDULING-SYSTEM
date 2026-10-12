from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope
from kit import DAY, act, needs, person, place, problem, rule, solved, start_of
from strategies import agreement, tiny_problems

STARTS = (0, 120, DAY, DAY + 120, 2 * DAY, 2 * DAY + 120)
LOPSIDED = [place("a1", 0, who="p"), place("a2", 120, who="p"), place("a3", DAY, who="p")]


def _three(
    starts: tuple[int, ...] = STARTS, weight: int = 1, scope: Scope | None = None
) -> Problem:
    return problem(
        [person("p")],
        [act(f"a{i}", 60, starts, needs()) for i in (1, 2, 3)],
        [rule("days", "day_distribution", hard=False, weight=weight, scope=scope)],
        days=3,
    )


def test_RUL_day_distribution_01_solver_spreads_across_days() -> None:
    solution = solved(_three())
    assert sorted(start_of(solution, f"a{i}") // DAY for i in (1, 2, 3)) == [0, 1, 2]


def test_RUL_day_distribution_02_and_03_formula_and_text() -> None:
    score = check(_three(weight=2), LOPSIDED)
    assert score.soft_total == 2 * (2 - 0)
    assert score.terms[0].details == (
        "Spread each resource's activities evenly across days: "
        "p has between 0 and 2 activities per day"
    )


def test_RUL_day_distribution_03_days_without_candidates_are_ignored() -> None:
    p = _three((0, 120, DAY, DAY + 120))
    assert check(p, LOPSIDED).soft_total == 1


def test_RUL_day_distribution_05_scope() -> None:
    assert check(_three(scope=Scope(resource_ids=("q",))), LOPSIDED).soft_total == 0


@agreement
@given(tiny_problems(keys=("day_distribution",)))
def test_RUL_day_distribution_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
