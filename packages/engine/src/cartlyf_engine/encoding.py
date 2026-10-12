"""What template encoders write into: the core decision variables plus one Rule per instance."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Literal

from ortools.sat.python import cp_model

from cartlyf_engine.domain import Problem
from cartlyf_engine.index import ProblemIndex

# Narrower than cp_model.LinearExprT, which also admits numpy integers and loses typing.
Expr = cp_model.LinearExpr | int
Constraint = cp_model.BoundedLinearExpression | cp_model.Constraint | bool
Lit = cp_model.BoolVarT
Bound = Literal["over", "under", "exact"]


@dataclass(frozen=True)
class Encoding:
    model: cp_model.CpModel
    problem: Problem
    index: ProblemIndex
    starts: Mapping[str, Mapping[int, cp_model.IntVar]]
    start: Mapping[str, cp_model.IntVar]
    uses: Mapping[tuple[str, str], cp_model.IntVar]
    _buckets: dict[tuple[str, tuple[int, ...]], cp_model.IntVar] = field(
        default_factory=dict[tuple[str, tuple[int, ...]], cp_model.IntVar], compare=False
    )

    def when(self, constraint: Constraint, *literals: Lit) -> None:
        """Add `constraint`, enforced only when every literal holds."""
        added = (
            constraint
            if isinstance(constraint, cp_model.Constraint)
            else self.model.add(constraint)
        )
        # The OR-Tools stub's catch-all `*args` overload of only_enforce_if is untyped.
        added.only_enforce_if(list(literals))  # pyright: ignore[reportUnknownMemberType]

    def bucket(self, activity_id: str, starts: Collection[int]) -> cp_model.IntVar | int:
        """1 exactly when the activity starts at one of `starts` (some of its candidate starts).
        One shared literal per (activity, start set); 0 or 1 when the set is empty or complete."""
        chosen = tuple(sorted(starts))
        literals = self.starts[activity_id]
        if not chosen:
            return 0
        if len(chosen) == len(literals):
            return 1
        if len(chosen) == 1:
            return literals[chosen[0]]
        key = (activity_id, chosen)
        if key not in self._buckets:
            b = self.model.new_bool_var("")
            self.model.add(b == sum(literals[s] for s in chosen))
            self._buckets[key] = b
        return self._buckets[key]

    def conj(
        self, a: cp_model.IntVar, b: cp_model.IntVar | int, bound: Bound
    ) -> cp_model.IntVar | int:
        """a AND b. "over" may read 1 when false and "under" may read 0 when true: use each only
        where that error can only raise a penalty or tighten a limit; "exact" otherwise."""
        if isinstance(b, int):
            return a if b else 0
        z = self.model.new_bool_var("")
        if bound != "under":
            self.model.add(z >= a + b - 1)
        if bound != "over":
            self.model.add(z <= a)
            self.model.add(z <= b)
        return z

    def assigned_at(
        self, activity_id: str, resource_id: str, starts: Collection[int], bound: Bound
    ) -> cp_model.IntVar | int:
        """The resource works the activity and it starts at one of `starts` (see `conj`)."""
        use = self.uses.get((activity_id, resource_id))
        if use is None:
            return 0
        return self.conj(use, self.bucket(activity_id, starts), bound)

    def breach(self, ok: Constraint, *when: Lit) -> cp_model.IntVar:
        """A literal forced to 1 whenever `ok` fails (given `when`). It may also be 1 when `ok`
        holds, so it only ever over-counts a minimised penalty."""
        v = self.model.new_bool_var("")
        self.when(ok, ~v, *when)
        return v


@dataclass
class Rule:
    """One constraint instance being encoded.

    Hard: constraints are enforced by `enforce`, a literal fixed true (or a solver assumption when
    explaining infeasibility). Soft: each breach adds an unweighted amount that is a lower bound
    on the true amount; minimisation makes it exact at the optimum (decision A)."""

    enc: Encoding
    enforce: cp_model.IntVar | None
    amounts: list[Expr] = field(default_factory=list[Expr])

    @property
    def hard(self) -> bool:
        return self.enforce is not None

    @property
    def model(self) -> cp_model.CpModel:
        return self.enc.model

    def add(self, constraint: Constraint, *when: cp_model.IntVar) -> None:
        if self.enforce is None:
            raise RuntimeError("only a hard rule adds constraints")
        self.enc.when(constraint, self.enforce, *when)

    def penalize(self, amount: Expr) -> None:
        self.amounts.append(amount)

    def at_most(self, expr: Expr, bound: int, upper: int) -> None:
        """expr <= bound; soft amount max(0, expr - bound). `upper` bounds expr from above."""
        if upper <= bound:
            return
        if self.enforce is not None:
            self.add(expr <= bound)
            return
        excess = self.model.new_int_var(0, upper - bound, "")
        self.model.add(excess >= expr - bound)
        self.amounts.append(excess)

    def at_least(self, expr: Expr, bound: int) -> None:
        """expr >= bound for a non-negative expr; soft amount max(0, bound - expr)."""
        if bound <= 0:
            return
        if self.enforce is not None:
            self.add(expr >= bound)
            return
        shortfall = self.model.new_int_var(0, bound, "")
        self.model.add(shortfall >= bound - expr)
        self.amounts.append(shortfall)
