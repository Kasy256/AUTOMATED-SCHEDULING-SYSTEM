"""Why is an activity placed where it is: what every alternative placement would break."""

from collections import Counter
from collections.abc import Iterator, Sequence

from pydantic import NonNegativeInt

from cartlyf_engine.domain import Activity, Assignment, Frozen, Id, Key, Problem
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.moves import MoveCheck, MoveChecker


class Alternative(Frozen):
    start: NonNegativeInt
    resources: dict[Key, tuple[Id, ...]]
    check: MoveCheck


class Binding(Frozen):
    """A rule that rules out (`blocks`) or makes costlier (`penalises`) some alternatives."""

    constraint_id: Id
    rule: str
    hard: bool
    blocks: NonNegativeInt
    penalises: NonNegativeInt


class Explanation(Frozen):
    activity_id: Id
    binding: tuple[Binding, ...]
    alternatives: tuple[Alternative, ...]


def explain_assignment(
    problem: Problem, assignments: Sequence[Assignment], activity_id: str
) -> Explanation:
    checker = MoveChecker(problem, assignments)
    activity = checker.index.activities.get(activity_id)
    current = checker.placed(activity_id)
    if activity is None or current is None:
        raise ValueError(f"{activity_id} is not placed")
    alternatives = tuple(
        Alternative(start=option.start, resources=option.resources, check=checker.check(option))
        for option in _options(checker.index, activity, current)
    )
    blocks: Counter[str] = Counter()
    penalises: Counter[str] = Counter()
    for alternative in alternatives:
        blocks.update({b.constraint_id for b in alternative.check.broken})
        penalises.update(p.constraint_id for p in alternative.check.penalties if p.after > p.before)
    binding = sorted(
        (
            Binding(
                constraint_id=c,
                rule=checker.rule_text(c),
                hard=checker.is_hard(c),
                blocks=blocks[c],
                penalises=penalises[c],
            )
            for c in blocks.keys() | penalises.keys()
        ),
        key=lambda b: (not b.hard, -b.blocks, -b.penalises, b.constraint_id),
    )
    return Explanation(activity_id=activity_id, binding=tuple(binding), alternatives=alternatives)


def _options(index: ProblemIndex, activity: Activity, current: Assignment) -> Iterator[Assignment]:
    """Every other start with the same resources, then every single-resource swap per role."""
    for start in activity.candidate_starts:
        if start != current.start:
            yield current.model_copy(update={"start": start})
    for req in activity.requirements:
        chosen = current.resources.get(req.role, ())
        swappable = [r for r in chosen if r not in req.fixed_resource_ids]
        for candidate in index.eligible(activity.id, req.role):
            if candidate in chosen:
                continue
            if swappable:
                for out in swappable:
                    picked = tuple(candidate if r == out else r for r in chosen)
                    yield current.model_copy(
                        update={"resources": {**current.resources, req.role: picked}}
                    )
            elif len(chosen) < req.count_max:
                yield current.model_copy(
                    update={"resources": {**current.resources, req.role: (*chosen, candidate)}}
                )
