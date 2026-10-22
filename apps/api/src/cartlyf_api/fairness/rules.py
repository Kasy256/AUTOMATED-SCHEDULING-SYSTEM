from collections.abc import Sequence

from cartlyf_engine.domain import ConstraintInstance
from cartlyf_engine.templates import fairness


def fairness_rules(
    constraints: Sequence[ConstraintInstance],
) -> list[tuple[ConstraintInstance, fairness.Params]]:
    return [
        (c, fairness.Params.model_validate(c.params))
        for c in constraints
        if c.template_key == fairness.SPEC.key
    ]
