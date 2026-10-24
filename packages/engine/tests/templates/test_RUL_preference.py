from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Resource, Scope
from kit import act, needs, person, place, problem, rule, solved, start_of, who, win
from strategies import agreement, tiny_problems


def _calendar(*people: Resource, scope: Scope | None = None) -> Problem:
    return problem(
        people,
        [act("a1", 60, [0, 120], needs())],
        [rule("pref", "preference", hard=False, weight=2, source="calendar", scope=scope)],
    )


def _explicit(mode: str) -> Problem:
    return problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs(), series="s1")],
        [
            rule(
                "pref",
                "preference",
                hard=False,
                weight=4,
                source="explicit",
                pairs=[{"resource_id": "p", "series_id": "s1", "mode": mode}],
            )
        ],
    )


def test_RUL_preference_01_solver_avoids_avoided_time() -> None:
    assert start_of(solved(_calendar(person("p", avoided=[win(0, 60)]))), "a1") == 120


def test_RUL_preference_01_solver_uses_preferred_time() -> None:
    assert start_of(solved(_calendar(person("p", preferred=[win(0, 60)]))), "a1") == 0


def test_RUL_preference_02_and_03_calendar_formula_and_text() -> None:
    p = _calendar(person("p", avoided=[win(0, 60)], preferred=[win(120, 240)]))
    score = check(p, [place("a1", 0, who="p")])
    assert score.soft_total == 2 * 2
    assert score.terms[0].details == (
        "Respect preferred and avoided times: a1 for p overlaps an avoided time; "
        "Respect preferred and avoided times: a1 for p is outside preferred times"
    )


def test_RUL_preference_03_explicit_pairs() -> None:
    assert who(solved(_explicit("prefer")), "a1") == ("p",)
    assert who(solved(_explicit("avoid")), "a1") == ("q",)
    score = check(_explicit("prefer"), [place("a1", 0, who="q")])
    assert (score.soft_total, score.terms[0].details) == (
        4,
        "Respect preferred and avoided assignments: p is not on a1, which it prefers",
    )
    assert check(_explicit("avoid"), [place("a1", 0, who="p")]).terms[0].details == (
        "Respect preferred and avoided assignments: p is on a1, which it should avoid"
    )


def test_RUL_preference_05_scope() -> None:
    p = _calendar(person("p", avoided=[win(0, 60)]), scope=Scope(resource_ids=("q",)))
    score = check(p, [place("a1", 0, who="p")])
    assert [(t.constraint_id, t.penalty) for t in score.terms] == [("pref", 0)]


@agreement
@given(tiny_problems(keys=("preference",)))
def test_RUL_preference_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
