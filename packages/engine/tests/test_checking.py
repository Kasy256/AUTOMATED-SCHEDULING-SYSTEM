from cartlyf_engine.checking import CheckContext
from cartlyf_engine.index import ProblemIndex
from kit import act, needs, person, place, problem


def test_place_and_unplace_keep_the_indexes_consistent() -> None:
    p = problem(
        [person("p"), person("q")], [act("a1", 60, [0, 120], needs()), act("a2", 60, [0], needs())]
    )
    ctx = CheckContext(p, ProblemIndex(p), {})
    ctx.place(place("a1", 120, who="p"))
    ctx.place(place("a2", 0, who="p"))
    assert [a.id for a in ctx.work("p")] == ["a2", "a1"]
    assert ctx.holders("a1") == frozenset({"p"})
    ctx.unplace("a1")
    assert [a.id for a in ctx.work("p")] == ["a2"]
    assert ctx.holders("a1") == frozenset()
    assert set(ctx.placed) == {"a2"}
    built = CheckContext(p, ProblemIndex(p), {"a2": place("a2", 0, who="p")})
    assert built.work("p") == ctx.work("p") and built.holders("a2") == ctx.holders("a2")
