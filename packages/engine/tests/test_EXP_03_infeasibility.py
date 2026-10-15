from cartlyf_engine.domain import Pin
from cartlyf_engine.infeasibility import Conflict, diagnose
from kit import act, needs, person, problem, rule, win


def test_EXP_03_names_the_rule_and_ranks_the_proven_fix_first() -> None:
    p = problem(
        [person("p")],
        [act(f"a{i}", 60, [0, 120], needs(), series="s1") for i in (1, 2)],
        [
            rule("spread", "spread", max_per_day=1),
            rule("rest", "min_rest", minutes=30),  # satisfiable on its own: not a conflict
        ],
        days=1,
    )
    report = diagnose(p, time_limit_s=10)
    assert report.conflicts == (
        Conflict(id="spread", kind="rule", text="Activities of a series: at most 1 per day"),
    )
    first = report.relaxations[0]
    assert (first.kind, first.target, first.fixes) == ("switch_to_soft", "spread", True)
    suggested = {(r.kind, r.target, r.fixes) for r in report.relaxations}
    assert ("change_param", "spread", None) in suggested


def test_EXP_03_core_only_infeasibility_suggests_adding_a_resource() -> None:
    p = problem([person("p")], [act("a1", 60, [0], needs(count=2))])
    report = diagnose(p, time_limit_s=10)
    (conflict,) = report.conflicts
    assert conflict.kind == "requirement"
    assert conflict.text == "Enough resources for role 'who' of type person"
    first = report.relaxations[0]
    assert (first.kind, first.fixes) == ("add_resource", True)
    assert first.text == "Add a resource for role 'who' of type person"


def test_EXP_03_unavailability_and_pins_are_named() -> None:
    p = problem(
        [person("p", unavailable=[win(0, 60)])],
        [act("a1", 60, [0, 60], needs(fixed=["p"]), pin=Pin(start=0))],
    )
    report = diagnose(p, time_limit_s=10)
    assert {c.id for c in report.conflicts} == {"core:unavailable:p", "core:pin:a1"}
    assert {(r.kind, r.fixes) for r in report.relaxations} == {
        ("free_resource", True),
        ("unpin", True),
    }


def test_EXP_03_feasible_problem_gives_an_empty_report() -> None:
    p = problem([person("p")], [act("a1", 60, [0], needs())])
    report = diagnose(p, time_limit_s=10)
    assert (report.conflicts, report.relaxations) == ((), ())
