from typing import cast

from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.synthetic import synthetic_problem

# Measured 2026-10-12 (lean encoding, feasible generator); guards against helper-literal blow-ups.
TERMS_PER_ACTIVITY_CEILING = 755


def linear_terms(problem_size: tuple[int, int, int]) -> int:
    acts, res, days = problem_size
    model = compile_problem(
        synthetic_problem(seed=1, activities=acts, resources=res, days=days)
    ).model
    proto = model.proto
    # OR-Tools' proto stub leaves message fields untyped.
    return sum(
        len(cast("list[int]", c.linear.vars))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        for c in proto.constraints  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    )


def test_linear_terms_per_activity_stay_under_the_ceiling() -> None:
    terms = linear_terms((400, 120, 10))
    print(f"\nlinear terms for 400 activities: {terms} ({terms / 400:.0f} per activity)")
    assert terms / 400 <= TERMS_PER_ACTIVITY_CEILING
