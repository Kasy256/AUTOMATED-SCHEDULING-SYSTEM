"""What template encoders write into: the core decision variables plus one Rule per instance."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from cartlyf_engine.domain import Problem
from cartlyf_engine.index import ProblemIndex

# Narrower than cp_model.LinearExprT, which also admits numpy integers and loses typing.
Expr = cp_model.LinearExpr | int
Constraint = cp_model.BoundedLinearExpression | cp_model.Constraint | bool
Lit = cp_model.BoolVarT


@dataclass(frozen=True)
class Encoding:
    model: cp_model.CpModel
    problem: Problem
    index: ProblemIndex
    starts: Mapping[str, Mapping[int, cp_model.IntVar]]
    start: Mapping[str, cp_model.IntVar]
    uses: Mapping[tuple[str, str], cp_model.IntVar]

    def when(self, constraint: Constraint, *literals: Lit) -> None:
        """Add `constraint`, enforced only when every literal holds."""
        added = (
            constraint
            if isinstance(constraint, cp_model.Constraint)
            else self.model.add(constraint)
        )
        # The OR-Tools stub's catch-all `*args` overload of only_enforce_if is untyped.
        added.only_enforce_if(list(literals))  # pyright: ignore[reportUnknownMemberType]

    def starts_in(self, activity_id: str, starts: Collection[int]) -> Expr:
        """1 if the activity starts at one of `starts` (candidate starts), else 0."""
        return sum(self.starts[activity_id][s] for s in starts)

    def both(self, a: cp_model.IntVar, b: Expr) -> cp_model.IntVar:
        """A literal equal to a AND b, where b is a 0/1 expression."""
        z = self.model.new_bool_var("")
        self.model.add(z <= a)
        self.model.add(z <= b)
        self.model.add(z >= a + b - 1)
        return z

    def assigned_at(
        self, activity_id: str, resource_id: str, starts: Collection[int]
    ) -> cp_model.IntVar | int:
        """Literal: the resource works the activity and it starts at one of `starts`."""
        use = self.uses.get((activity_id, resource_id))
        if use is None or not starts:
            return 0
        if len(starts) == len(self.starts[activity_id]):
            return use
        return self.both(use, self.starts_in(activity_id, starts))

    def holds(self, constraint: Constraint, negation: Constraint) -> cp_model.IntVar:
        """A literal that is 1 exactly when `constraint` holds; `negation` is its complement."""
        b = self.model.new_bool_var("")
        self.when(constraint, b)
        self.when(negation, ~b)
        return b

    def gate(self, expr: Expr, lit: cp_model.IntVar, upper: int) -> cp_model.IntVar:
        """`expr` when `lit` is 1, else 0; `expr` must lie in 0..upper."""
        v = self.model.new_int_var(0, upper, "")
        self.when(v == expr, lit)
        self.when(v == 0, ~lit)
        return v


@dataclass
class Rule:
    """One constraint instance being encoded.

    Hard: constraints are enforced by `enforce`, the instance's assumption literal. Soft: each
    breach adds an exact (not merely bounding) unweighted amount, so the objective equals the
    checker's total for every solution the solver reports."""

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
        self.model.add_max_equality(excess, [expr - bound, 0])
        self.amounts.append(excess)

    def at_least(self, expr: Expr, bound: int) -> None:
        """expr >= bound for a non-negative expr; soft amount max(0, bound - expr)."""
        if bound <= 0:
            return
        if self.enforce is not None:
            self.add(expr >= bound)
            return
        shortfall = self.model.new_int_var(0, bound, "")
        self.model.add_max_equality(shortfall, [bound - expr, 0])
        self.amounts.append(shortfall)

    def forbid(self, violated: cp_model.IntVar) -> None:
        """`violated` is a literal that is 1 exactly when the rule is broken once."""
        if self.enforce is not None:
            self.add(violated == 0)
        else:
            self.amounts.append(violated)
