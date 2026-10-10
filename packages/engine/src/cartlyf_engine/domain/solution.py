from enum import StrEnum

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from cartlyf_engine.domain.base import Frozen, Id, Key


class Assignment(Frozen):
    activity_id: Id
    start: NonNegativeInt
    resources: dict[Key, tuple[Id, ...]] = Field(default_factory=dict)


class PenaltyTerm(Frozen):
    constraint_id: Id
    penalty: NonNegativeInt
    details: str = ""


class Score(Frozen):
    hard_violations: NonNegativeInt
    soft_total: NonNegativeInt
    terms: tuple[PenaltyTerm, ...] = ()


class SolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class SolveStats(Frozen):
    wall_time_s: NonNegativeFloat
    objective_bound: float | None = None
    gap: float | None = None


class Solution(Frozen):
    status: SolveStatus
    assignments: tuple[Assignment, ...] = ()
    score: Score
    conflicts: tuple[Id, ...] = ()
    stats: SolveStats
