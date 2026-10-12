import pytest

from cartlyf_engine.checker import check
from cartlyf_engine.construct import construct
from cartlyf_engine.domain import Pin, Problem, Scope
from cartlyf_engine.synthetic import synthetic_problem
from kit import DAY, act, needs, person, problem, rule, win


def _verified(p: Problem) -> None:
    plan = construct(p)
    assert len(plan) == len(p.activities)
    assert check(p, plan).hard_violations == 0


def test_respects_core_rules() -> None:
    _verified(
        problem(
            [person("p", unavailable=[win(0, 60)]), person("q", "x")],
            [
                act("a1", 60, [0, 60], needs()),
                act("a2", 60, [0, 60], needs()),
                act("a3", 60, [0], needs("who", "person", "x")),
            ],
        )
    )


def test_hard_rules_block_options() -> None:
    p = problem(
        [person("p")],
        [act(f"a{i}", 60, [0, 120, DAY], needs(), series="s1") for i in (1, 2)],
        [
            rule("cap", "max_load", period="day", max_count=1),
            rule("spread", "spread", max_per_day=1),
        ],
    )
    _verified(p)


def test_pins_first_and_unplaceable_pins_are_skipped() -> None:
    p = problem(
        [person("p", unavailable=[win(0, 60)]), person("q")],
        [
            act("a1", 60, [0, 60], needs(), pin=Pin(start=0, resources={"who": ("p",)})),
            act("a2", 60, [0], needs()),
        ],
    )
    plan = construct(p)
    assert [a.activity_id for a in plan] == ["a2"]


def test_soft_requirement_shortfall_does_not_block() -> None:
    p = problem(
        [person("p")], [act("a1", 60, [0], needs(count=2, count_max=2, hard=False, weight=1))]
    )
    plan = construct(p)
    assert len(plan) == 1 and plan[0].resources["who"] == ("p",)


def test_lower_bound_rules_never_block() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs())],
        [rule("min", "min_load", period="horizon", min_count=1, scope=Scope(resource_ids=("q",)))],
    )
    assert len(construct(p)) == 1


def test_deterministic_and_stoppable() -> None:
    p = problem(
        [person("p"), person("q")], [act(f"a{i}", 60, [0, 60, 120], needs()) for i in range(5)]
    )
    assert construct(p) == construct(p)
    assert construct(p, keep_going=lambda: False) == ()
    assert len(construct(p, max_evaluations=2)) <= 2


def test_hard_findings_never_grow() -> None:
    p = problem(
        [person("p"), person("q")],
        [
            act(f"a{i}", 60, [0, 120, 240], needs(), series="s1" if i % 2 else "s2")
            for i in range(6)
        ],
        [rule("cap", "max_load", period="day", max_count=2), rule("rest", "min_rest", minutes=60)],
    )
    plan = construct(p)
    assert check(p, plan).hard_violations == len(p.activities) - len(plan)  # only "not placed"


@pytest.mark.benchmark
def test_construct_places_the_eng08_instance() -> None:
    p = synthetic_problem(seed=1)
    plan = construct(p)
    assert len(plan) == len(p.activities)
    assert check(p, plan).hard_violations == 0


def test_two_roles_from_one_pool_are_both_filled() -> None:
    p = problem(
        [person("p1"), person("p2"), person("p3")],
        [act("a1", 60, [0, 60], needs("lead"), needs("assist"))],
    )
    _verified(p)


def test_a_role_needing_several_tries_other_resources() -> None:
    people = [person(f"p{i}") for i in range(10)]
    p = problem(
        people,
        [act("a0", 60, [0], needs()), act("a1", 60, [120], needs(count=2, count_max=2))],
        [rule("cap", "max_load", period="horizon", max_count=1)],
    )
    _verified(p)
