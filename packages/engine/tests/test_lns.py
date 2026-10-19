from functools import cache

from cartlyf_engine.checker import check
from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.construct import construct
from cartlyf_engine.domain import Assignment, Pin, Problem, SolveOptions
from cartlyf_engine.lns import Incumbent, improve
from cartlyf_engine.solve import solve
from kit import DAY, act, needs, person, problem, rule

SHIFTS = {"Day": 420, "Evening": 900, "Night": 1380}
OPTIONS = SolveOptions(time_limit_s=60, seed=0, num_workers=1)


def rota(people: int = 8, days: int = 7, pin_first_night: str | None = None) -> Problem:
    """Three 8-hour shifts a day for two people each, nights shared fairly; first-fit piles
    nights onto the first people."""
    activities = [
        act(
            f"{slot} {d}",
            480,
            [d * DAY + start],
            needs(count=2, count_max=2, hard=False, weight=100),
            attrs={"slot": slot},
            pin=(
                Pin(resources={"who": (pin_first_night,)})
                if pin_first_night and (slot, d) == ("Night", 0)
                else None
            ),
        )
        for d in range(days)
        for slot, start in SHIFTS.items()
    ]
    rules = [
        rule("rest", "min_rest", minutes=660),
        rule(
            "fair",
            "fairness",
            hard=False,
            weight=10,
            counter="nights",
            activity_filter={"attrs": [{"attr": "slot", "op": "eq", "value": "Night"}]},
            lookback_days=84,
        ),
    ]
    return problem([person(f"p{i:02}") for i in range(people)], activities, rules, days=days + 1)


def improved(p: Problem, start: tuple[Assignment, ...]) -> Incumbent:
    compiled = compile_problem(p)
    result, _ = improve(
        p,
        compiled,
        Incumbent(start, check(p, start), None),
        OPTIONS,
        wall_budget_s=OPTIONS.time_limit_s,
    )
    return result


@cache
def greedy() -> tuple[Problem, tuple[Assignment, ...], Incumbent]:
    p = rota()
    start = construct(p)
    return p, start, improved(p, start)


def test_lns_improves_a_greedy_start() -> None:
    p, start, result = greedy()
    before = check(p, start)
    assert before.hard_violations == 0 and before.soft_total > 0
    assert result.score == check(p, result.assignments)
    assert result.score.hard_violations == 0
    assert result.score.soft_total < before.soft_total


def test_lns_is_deterministic() -> None:
    p, start, result = greedy()
    assert improved(p, start) == result
    first, second = solve(p, OPTIONS), solve(p, OPTIONS)
    assert (first.assignments, first.score) == (second.assignments, second.score)


def test_lns_never_frees_pins() -> None:
    p = rota(pin_first_night="p00")
    start = construct(p)
    [pinned] = [a for a in start if a.activity_id == "Night 0"]
    result = improved(p, start)
    assert result.score.soft_total < check(p, start).soft_total
    assert [a for a in result.assignments if a.activity_id == "Night 0"] == [pinned]


def test_lns_never_worse_than_start() -> None:
    p, _, best = greedy()
    again = improved(p, best.assignments)
    assert (again.score.hard_violations, again.score.soft_total) <= (
        best.score.hard_violations,
        best.score.soft_total,
    )
    solution = solve(p, OPTIONS)
    assert solution.score.soft_total <= check(p, construct(p)).soft_total
