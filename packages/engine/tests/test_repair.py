from cartlyf_engine.construct import construct
from kit import act, needs, person, place, problem, rule, solved, win


def test_construct_prefers_the_baseline() -> None:
    p = problem([person("p"), person("q")], [act("a1", 60, [0, 120, 240], needs())])
    assert construct(p) == (place("a1", 0, who="p"),)
    assert construct(p, prefer={"a1": place("a1", 240, who="q")}) == (place("a1", 240, who="q"),)


def test_construct_keeps_what_still_fits_of_the_baseline() -> None:
    p = problem(
        [person("p", unavailable=[win(240, 300)]), person("q")],
        [act("a1", 60, [0, 120, 240], needs())],
    )
    assert construct(p, prefer={"a1": place("a1", 240, who="p")}) == (place("a1", 240, who="q"),)


def test_repair_solve_changes_only_the_broken_assignment() -> None:
    people = [person(f"p{i}") for i in range(3)]
    acts = [act(f"a{i}", 60, [h * 60 for h in range(8)], needs()) for i in range(12)]
    first = solved(problem(people, acts))
    victim = first.assignments[0]
    (blocked_id,) = victim.resources["who"]
    gone = [win(victim.start, victim.start + 60)]
    blocked = [person(r.id, unavailable=gone) if r.id == blocked_id else r for r in people]
    stay = rule("stay", "stability", hard=False, weight=10, per_change=1, per_resource_change=1)
    repaired = solved(problem(blocked, acts, [stay], baseline=first.assignments))
    changed = [
        a.activity_id
        for a, b in zip(repaired.assignments, first.assignments, strict=True)
        if a != b
    ]
    assert changed == [victim.activity_id]
