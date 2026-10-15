"""What one planner move would change, checked on its neighbourhood only. No solver."""

from collections.abc import Sequence

from pydantic import NonNegativeInt

from cartlyf_engine.checker import check
from cartlyf_engine.checking import CheckContext
from cartlyf_engine.domain import (
    CORE_RULES,
    REQUIREMENTS_TERM,
    Assignment,
    Frozen,
    Id,
    Problem,
    Score,
    Violation,
)
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.neighbourhood import Neighbourhood, Scoped
from cartlyf_engine.templates.registry import describe


class Broken(Frozen):
    constraint_id: Id
    rule: str
    message: str
    activity_ids: tuple[Id, ...] = ()
    resource_ids: tuple[Id, ...] = ()


class PenaltyChange(Frozen):
    constraint_id: Id
    rule: str
    before: NonNegativeInt
    after: NonNegativeInt


class MoveCheck(Frozen):
    """`valid`: the move adds no hard violation. `broken`: each one it adds."""

    valid: bool
    broken: tuple[Broken, ...] = ()
    penalties: tuple[PenaltyChange, ...] = ()


class MoveChecker:
    """Checks moves against one set of assignments; build once, ask many times."""

    def __init__(self, problem: Problem, assignments: Sequence[Assignment]) -> None:
        self.index = ProblemIndex(problem)
        placed = {a.activity_id: a for a in assignments if a.activity_id in self.index.activities}
        self._ctx = CheckContext(problem, self.index, placed)
        self._hood = Neighbourhood(problem, problem.constraints)
        self._rules = {c.id: c for c in problem.constraints}

    def placed(self, activity_id: str) -> Assignment | None:
        return self._ctx.placed.get(activity_id)

    def rule_text(self, constraint_id: str) -> str:
        instance = self._rules.get(constraint_id)
        if instance is not None:
            return describe(instance)
        return CORE_RULES.get(constraint_id, constraint_id)

    def is_hard(self, constraint_id: str) -> bool:
        instance = self._rules.get(constraint_id)
        if instance is not None:
            return instance.hard
        return constraint_id != REQUIREMENTS_TERM

    def check(self, move: Assignment) -> MoveCheck:
        activity_id = move.activity_id
        if activity_id not in self.index.activities:
            raise ValueError(f"unknown activity {activity_id}")
        held = {r for ids in move.resources.values() for r in ids} | self._ctx.holders(activity_id)
        rules = self._hood.rules_for(activity_id)
        # Whole-scope rules widen a neighbourhood to their scope; checking them apart keeps the
        # core and every other rule on the small one.
        before, after = self._scores(move, held, [r for r in rules if not r.resources])
        wide = [r for r in rules if r.resources]
        if wide:
            ids = {r.instance.id for r in wide}
            wide_before, wide_after = self._scores(move, held, wide)
            before = _merged(before, wide_before, ids)
            after = _merged(after, wide_after, ids)
        old = set(before.violations)
        broken = tuple(self._broken(v) for v in after.violations if v not in old)
        return MoveCheck(valid=not broken, broken=broken, penalties=self._changes(before, after))

    def _scores(self, move: Assignment, held: set[str], rules: list[Scoped]) -> tuple[Score, Score]:
        local = self._hood.around(self._ctx, move.activity_id, held, rules)
        placed = local.placed
        before = check(local.problem, tuple(placed.values()), self.index)
        after = check(
            local.problem, tuple((placed | {move.activity_id: move}).values()), self.index
        )
        return before, after

    def _broken(self, violation: Violation) -> Broken:
        return Broken(
            constraint_id=violation.constraint_id,
            rule=self.rule_text(violation.constraint_id),
            message=violation.message,
            activity_ids=violation.activity_ids,
            resource_ids=violation.resource_ids,
        )

    def _changes(self, before: Score, after: Score) -> tuple[PenaltyChange, ...]:
        old = {t.constraint_id: t.penalty for t in before.terms}
        return tuple(
            PenaltyChange(
                constraint_id=t.constraint_id,
                rule=self.rule_text(t.constraint_id),
                before=old.get(t.constraint_id, 0),
                after=t.penalty,
            )
            for t in after.terms
            if t.penalty != old.get(t.constraint_id, 0)
        )


def _merged(core: Score, wide: Score, ids: set[str]) -> Score:
    """`core`'s results plus `wide`'s for the whole-scope rules `ids`."""
    violations = (*core.violations, *(v for v in wide.violations if v.constraint_id in ids))
    terms = (*core.terms, *(t for t in wide.terms if t.constraint_id in ids))
    return Score(
        hard_violations=len(violations),
        soft_total=sum(t.penalty for t in terms),
        terms=terms,
        violations=violations,
    )
