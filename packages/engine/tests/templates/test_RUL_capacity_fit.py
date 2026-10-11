from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Activity, Problem, Scope, SolveStatus
from kit import act, group, needs, place, problem, room, rule, solve1, solved, who
from strategies import agreement, tiny_problems


def _lecture(id: str = "a1", grp: str = "g", series: str | None = None) -> Activity:
    return act(
        id, 60, [0], needs("group", "group", fixed=[grp]), needs("room", "room"), series=series
    )


def test_RUL_capacity_fit_01_hard_picks_a_room_that_fits() -> None:
    p = problem(
        [group("g", 30), room("small", 20), room("big", 40)],
        [_lecture()],
        [rule("fit", "capacity_fit")],
    )
    assert who(solved(p), "a1", "room") == ("big",)


def test_RUL_capacity_fit_01_hard_infeasible_without_a_room_that_fits() -> None:
    p = problem([group("g", 30), room("small", 20)], [_lecture()], [rule("fit", "capacity_fit")])
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("fit",))


def test_RUL_capacity_fit_02_checker_explains_the_violation() -> None:
    p = problem([group("g", 30), room("small", 20)], [_lecture()], [rule("fit", "capacity_fit")])
    score = check(p, [place("a1", 0, group="g", room="small")])
    assert [(v.constraint_id, v.message) for v in score.violations] == [
        ("fit", "A space must seat the activity's headcount: small seats 20, a1 has 30")
    ]


def test_RUL_capacity_fit_03_soft_penalises_seats_off_both_ways() -> None:
    rooms = [room("r20", 20), room("r35", 35), room("r50", 50)]
    p = problem(
        [group("g", 30), *rooms], [_lecture()], [rule("fit", "capacity_fit", hard=False, weight=2)]
    )
    penalties = {r.id: check(p, [place("a1", 0, group="g", room=r.id)]).soft_total for r in rooms}
    assert penalties == {"r20": 20, "r35": 10, "r50": 40}
    assert who(solved(p), "a1", "room") == ("r35",)


def test_RUL_capacity_fit_03_headcount_from_an_activity_attr() -> None:
    p = problem(
        [room("r20", 20), room("r50", 50)],
        [act("a1", 60, [0], needs("room", "room"), attrs={"heads": 45})],
        [rule("fit", "capacity_fit", headcount_from="activity_attr", headcount_attr="heads")],
    )
    assert who(solved(p), "a1", "room") == ("r50",)


def test_RUL_capacity_fit_05_series_scope() -> None:
    p = problem(
        [group("g", 30), group("h", 30), room("small", 20), room("big", 40)],
        [_lecture("a1", "g", "s1"), _lecture("a2", "h", "s2")],
        [rule("fit", "capacity_fit", scope=Scope(series_ids=("s1",)))],
    )
    solution = solved(p)
    assert (who(solution, "a1", "room"), who(solution, "a2", "room")) == (("big",), ("small",))


def test_RUL_capacity_fit_05_resource_scope_limits_the_spaces_checked() -> None:
    p = problem(
        [group("g", 30), room("small", 20)],
        [_lecture()],
        [rule("fit", "capacity_fit", scope=Scope(resource_ids=("elsewhere",)))],
    )
    assert who(solved(p), "a1", "room") == ("small",)


@agreement
@given(tiny_problems(keys=("capacity_fit",)))
def test_RUL_capacity_fit_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
