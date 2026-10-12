from typing import cast

from ortools.sat.python import cp_model

from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.domain import Pin, SolveStatus
from kit import DAY, act, needs, person, problem, rule, solve1, solved, start_of, who, win


def test_ENG_02_no_double_booking() -> None:
    p = problem([person("p")], [act("a1", 60, [0, 60], needs()), act("a2", 60, [0, 60], needs())])
    solution = solved(p)
    assert {start_of(solution, "a1"), start_of(solution, "a2")} == {0, 60}
    clash = problem([person("p")], [act("a1", 60, [0], needs()), act("a2", 60, [30], needs())])
    assert solve1(clash).status is SolveStatus.INFEASIBLE


def test_ENG_02_concurrency_allows_up_to_its_limit() -> None:
    two = problem([person("c", concurrency=2)], [act(f"a{i}", 60, [0], needs()) for i in range(2)])
    solved(two)
    three = problem(
        [person("c", concurrency=2)], [act(f"a{i}", 60, [0], needs()) for i in range(3)]
    )
    assert solve1(three).status is SolveStatus.INFEASIBLE


def test_ENG_02_unavailable_windows_respected() -> None:
    p = problem([person("p", unavailable=[win(0, 61)])], [act("a1", 60, [0, 60, 120], needs())])
    assert start_of(solved(p), "a1") == 120


def test_ENG_02_overlapping_unavailable_windows_are_merged() -> None:
    p = problem(
        [person("p", unavailable=[win(0, 100), win(50, 200), win(200, 250)])],
        [act("a1", 60, [0, 300], needs())],
    )
    assert start_of(solved(p), "a1") == 300


def test_ENG_02_requirement_filters_respected() -> None:
    p = problem([person("p"), person("q", "x")], [act("a1", 60, [0], needs("who", "person", "x"))])
    assert who(solved(p), "a1") == ("q",)


def test_ENG_02_counts_within_min_and_max() -> None:
    p = problem(
        [person("p"), person("q"), person("r")],
        [act("a1", 60, [0], needs(count=2, count_max=2))],
    )
    assert len(who(solved(p), "a1")) == 2


def test_ENG_02_pins_respected() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0, 60], needs(), pin=Pin(start=60, resources={"who": ("q",)}))],
    )
    solution = solved(p)
    assert (start_of(solution, "a1"), who(solution, "a1")) == (60, ("q",))


def test_ENG_02_one_resource_cannot_fill_two_roles() -> None:
    p = problem([person("p")], [act("a1", 60, [0], needs("lead"), needs("assist"))])
    assert solve1(p).status is SolveStatus.INFEASIBLE


def test_core_only_infeasibility_has_no_conflicts() -> None:
    p = problem(
        [person("p"), person("q", "x")],
        [act("a1", 60, [0], needs("who", "person", "x", fixed=["p"]))],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts, solution.assignments) == (
        SolveStatus.INFEASIBLE,
        (),
        (),
    )


def test_empty_problem_is_optimal_and_empty() -> None:
    solution = solved(problem([], []))
    assert (solution.status, solution.assignments) == (SolveStatus.OPTIMAL, ())


def test_soft_requirement_shortfall_is_minimised() -> None:
    p = problem(
        [person("p")], [act("a1", 60, [0], needs(count=2, count_max=2, hard=False, weight=5))]
    )
    solution = solved(p)
    assert who(solution, "a1") == ("p",)
    assert solution.stats.objective == 5
    assert solution.score.terms[0].constraint_id == "core:requirements"


def test_solves_are_deterministic() -> None:
    p = problem(
        [person("p"), person("q")],
        [act(f"a{i}", 60, [0, 60, 120, DAY], needs()) for i in range(4)],
    )
    assert solve1(p).assignments == solve1(p).assignments


def test_main_model_has_no_assumptions_so_workers_can_run_in_parallel() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs())],
        [rule("cap", "max_load", period="day", max_count=1)],
    )
    assert _assumptions(compile_problem(p).model) == []
    assert len(_assumptions(compile_problem(p, assumptions=True).model)) == 1


def _assumptions(model: cp_model.CpModel) -> list[int]:
    # The OR-Tools proto stub leaves repeated fields untyped.
    return list(cast("list[int]", model.proto.assumptions))  # pyright: ignore[reportUnknownMemberType]
