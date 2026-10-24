from enum import StrEnum

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from cartlyf_engine.domain.base import Frozen, Id, Key

CORE_PLACEMENT = "core:placement"
CORE_REQUIREMENT = "core:requirement"
CORE_OVERLAP = "core:overlap"
CORE_UNAVAILABLE = "core:unavailable"
CORE_PIN = "core:pin"
REQUIREMENTS_TERM = "core:requirements"
CORE_RULES = {
    CORE_PLACEMENT: "Every activity is placed once, at one of its candidate starts",
    CORE_REQUIREMENT: "Every role is filled by enough matching resources",
    CORE_OVERLAP: "A resource is never in more activities at once than it can handle",
    CORE_UNAVAILABLE: "Resources are never scheduled while unavailable",
    CORE_PIN: "Pinned assignments stay where they are pinned",
    REQUIREMENTS_TERM: "Soft staffing requirements are filled",
}


class Assignment(Frozen):
    activity_id: Id
    start: NonNegativeInt
    resources: dict[Key, tuple[Id, ...]] = Field(default_factory=dict)


class PenaltyTerm(Frozen):
    constraint_id: Id
    penalty: NonNegativeInt
    details: str = ""


class Violation(Frozen):
    """A broken hard rule. Core rules use the reserved `core:*` ids above."""

    constraint_id: Id
    message: str
    activity_ids: tuple[Id, ...] = ()
    resource_ids: tuple[Id, ...] = ()


class Score(Frozen):
    hard_violations: NonNegativeInt
    soft_total: NonNegativeInt
    terms: tuple[PenaltyTerm, ...] = ()
    violations: tuple[Violation, ...] = ()


class SolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class SolveStats(Frozen):
    wall_time_s: NonNegativeFloat
    objective: int | None = None
    objective_bound: float | None = None
    gap: float | None = None


class Solution(Frozen):
    status: SolveStatus
    assignments: tuple[Assignment, ...] = ()
    score: Score
    conflicts: tuple[Id, ...] = ()
    stats: SolveStats
