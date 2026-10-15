from cartlyf_engine.checking import CheckContext
from cartlyf_engine.domain import Assignment, Problem, Scope
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.neighbourhood import Neighbourhood
from kit import act, needs, person, place, problem, rule


def _ctx(p: Problem, *placed: Assignment) -> CheckContext:
    return CheckContext(p, ProblemIndex(p), {a.activity_id: a for a in placed})


def test_neighbourhood_holds_the_series_and_shared_resources() -> None:
    p = problem(
        [person("p"), person("q"), person("r")],
        [
            act("a1", 60, [0], needs(), series="s1"),
            act("a2", 60, [120], needs(), series="s1"),
            act("a3", 60, [240], needs()),
            act("a4", 60, [360], needs()),
        ],
        [rule("rest", "min_rest", minutes=30)],
    )
    ctx = _ctx(
        p,
        place("a1", 0, who="p"),
        place("a2", 120, who="q"),
        place("a3", 240, who="p"),
        place("a4", 360, who="r"),
    )
    hood = Neighbourhood(p, p.constraints)
    local = hood.around(ctx, "a1", {"p"}, hood.rules_for("a1"))
    assert [a.id for a in local.problem.activities] == ["a1", "a2", "a3"]
    assert [r.id for r in local.problem.resources] == ["p", "q"]
    assert [c.id for c in local.problem.constraints] == ["rest"]


def test_whole_scope_rules_widen_to_their_scope() -> None:
    p = problem(
        [person("p"), person("q"), person("r")],
        [act("a1", 60, [0], needs()), act("a2", 60, [120], needs()), act("a3", 60, [240], needs())],
        [
            rule(
                "bal",
                "balance",
                hard=False,
                weight=1,
                measure="count",
                scope=Scope(resource_ids=("p", "r")),
            )
        ],
    )
    ctx = _ctx(p, place("a1", 0, who="p"), place("a2", 120, who="q"), place("a3", 240, who="r"))
    hood = Neighbourhood(p, p.constraints)
    local = hood.around(ctx, "a1", {"p"}, hood.rules_for("a1"))
    assert [a.id for a in local.problem.activities] == ["a1", "a2", "a3"]
    assert [r.id for r in local.problem.resources] == ["p", "q", "r"]
