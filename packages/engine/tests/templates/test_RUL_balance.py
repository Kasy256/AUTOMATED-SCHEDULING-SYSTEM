from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope
from kit import act, needs, person, place, problem, rule, solved, who
from strategies import agreement, tiny_problems

BOTH_ON_P = [place("a1", 0, who="p"), place("a2", 120, who="p")]


def _two(
    measure: str = "count", weight: int = 1, scope: Scope | None = None, extra: tuple[str, ...] = ()
) -> Problem:
    return problem(
        [person("p"), person("q"), *(person(e) for e in extra)],
        [act("a1", 60, [0], needs()), act("a2", 30, [120], needs())],
        [rule("bal", "balance", hard=False, weight=weight, measure=measure, scope=scope)],
    )


def test_RUL_balance_01_solver_evens_out_load() -> None:
    solution = solved(_two())
    assert {who(solution, "a1"), who(solution, "a2")} == {("p",), ("q",)}


def test_RUL_balance_02_and_03_formula_and_text() -> None:
    score = check(_two(weight=3), BOTH_ON_P)
    assert score.soft_total == 3 * 2
    assert (
        score.terms[0].details
        == "Even out activity counts across resources: load ranges from 0 (q) to 2 (p)"
    )
    assert check(_two("minutes"), BOTH_ON_P).soft_total == 90


def test_RUL_balance_05_scope() -> None:
    p = _two(scope=Scope(resource_ids=("p", "q")), extra=("r",))
    assert check(p, [place("a1", 0, who="p"), place("a2", 120, who="q")]).soft_total == 0


@agreement
@given(tiny_problems(keys=("balance",)))
def test_RUL_balance_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
