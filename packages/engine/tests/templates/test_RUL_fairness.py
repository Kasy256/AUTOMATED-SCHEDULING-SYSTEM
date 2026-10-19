from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import AttrValue, Problem, Resource, Scope
from cartlyf_engine.templates.fairness import counted
from kit import act, needs, person, place, problem, rule, solved, who, win
from strategies import agreement, tiny_problems

NIGHT: dict[str, AttrValue] = {"slot": "Night"}
BOTH_ON_P = [place("n1", 0, who="p"), place("n2", 120, who="p")]
ONE_EACH = [place("n1", 0, who="p"), place("n2", 120, who="q")]


def _nights(
    history: dict[str, int] | None = None,
    weight: int = 1,
    scope: Scope | None = None,
    extra: tuple[Resource, ...] = (),
) -> Problem:
    return problem(
        [person("p"), person("q"), *extra],
        [
            act("n1", 60, [0], needs(), attrs=NIGHT),
            act("n2", 60, [120], needs(), attrs=NIGHT),
            act("d1", 60, [300], needs(), attrs={"slot": "Day"}),
        ],
        [
            rule(
                "fair",
                "fairness",
                hard=False,
                weight=weight,
                scope=scope,
                counter="nights",
                activity_filter={"attrs": [{"attr": "slot", "op": "eq", "value": "Night"}]},
                lookback_days=84,
            )
        ],
        history={"fair": history} if history is not None else None,
    )


def test_RUL_fairness_01_history_steers_the_solver() -> None:
    solution = solved(_nights({"p": 2, "q": 0}))
    assert who(solution, "n1") == ("q",)
    assert who(solution, "n2") == ("q",)


def test_RUL_fairness_02_formula_includes_history() -> None:
    assert check(_nights({"p": 1}, weight=3), BOTH_ON_P).soft_total == 3 * 3


def test_RUL_fairness_03_text() -> None:
    score = check(_nights({"p": 1}), BOTH_ON_P)
    assert (
        score.terms[0].details
        == "Share nights fairly, counting the last 84 days: totals range from 0 (q) to 3 (p)"
    )


@agreement
@given(tiny_problems(keys=("fairness",)))
def test_RUL_fairness_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)


def test_RUL_fairness_05_scope_and_eligibility() -> None:
    scoped = _nights(scope=Scope(resource_ids=("p", "q")), extra=(person("r"),))
    assert check(scoped, ONE_EACH).soft_total == 0
    away = _nights(extra=(person("u", unavailable=[win(0, 180)]),))
    assert check(away, ONE_EACH).soft_total == 0


def test_fairness_counted_lists_matching_starts() -> None:
    p = _nights()
    placed = [place("n1", 0, who="p"), place("d1", 300, who="p")]
    assert counted(p, p.constraints[0], placed) == {"p": [0]}


def test_fairness_without_history_is_balance_on_matches() -> None:
    assert check(_nights(), [*BOTH_ON_P, place("d1", 300, who="q")]).soft_total == 2
    assert check(_nights(), ONE_EACH).soft_total == 0
