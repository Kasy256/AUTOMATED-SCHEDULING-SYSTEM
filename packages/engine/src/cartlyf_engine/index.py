"""Pure lookups shared by the compiler and the checker: eligibility and time attribution.
No rule logic lives here."""

from collections.abc import Sequence
from typing import Literal

from cartlyf_engine.domain import (
    CORE_REQUIREMENT,
    Activity,
    Problem,
    Resource,
    ResourceFilter,
    Window,
    resource_matches,
)

Period = Literal["day", "week", "horizon"]


def window_index(windows: Sequence[Window], minute: int) -> int | None:
    for i, window in enumerate(windows):
        if window.start <= minute < window.end:
            return i
    return None


class ProblemIndex:
    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        self.activities: dict[str, Activity] = {a.id: a for a in problem.activities}
        self.resources: dict[str, Resource] = {r.id: r for r in problem.resources}
        self._horizon = (Window(start=0, end=problem.horizon_minutes),)
        matching: dict[ResourceFilter, tuple[str, ...]] = {}
        self._eligible: dict[tuple[str, str], tuple[str, ...]] = {}
        self._candidates: dict[str, frozenset[str]] = {}
        for activity in problem.activities:
            for req in activity.requirements:
                if req.filter not in matching:
                    matching[req.filter] = tuple(
                        r.id for r in problem.resources if resource_matches(r, req.filter)
                    )
                eligible = matching[req.filter]
                fixed = req.fixed_resource_ids
                # When the fixed resources fill the role, no other resource can ever be picked.
                if fixed and len(fixed) == req.count_max:
                    eligible = tuple(r for r in eligible if r in fixed)
                self._eligible[activity.id, req.role] = eligible
            self._candidates[activity.id] = frozenset(
                r for req in activity.requirements for r in self._eligible[activity.id, req.role]
            )

    def eligible(self, activity_id: str, role: str) -> tuple[str, ...]:
        """Resources that may fill the role: those matching its filter, in problem order, or only
        the fixed ones when they fill it."""
        return self._eligible[activity_id, role]

    def candidates(self, activity_id: str) -> frozenset[str]:
        """Resources that may work the activity in some role."""
        return self._candidates[activity_id]

    def periods(self, period: Period) -> tuple[Window, ...]:
        match period:
            case "day":
                return self.problem.day_windows
            case "week":
                return self.problem.week_windows
            case "horizon":
                return self._horizon

    def named(self, key: str) -> tuple[Window, ...]:
        return self.problem.named_windows[key]

    def attribute(self, minute: int, period: Period, window: str | None) -> int | None:
        """The period an activity starting at `minute` counts in; None if outside `window`."""
        if window is not None and window_index(self.named(window), minute) is None:
            return None
        return window_index(self.periods(period), minute)


def requirement_pools(problem: Problem) -> dict[tuple[str, ResourceFilter], str]:
    """Hard minimum counts grouped by role and filter, so infeasibility can name a staffing pool."""
    pools: dict[tuple[str, ResourceFilter], str] = {}
    for activity in problem.activities:
        for req in activity.requirements:
            if req.hard and req.count_min > 0 and (req.role, req.filter) not in pools:
                pools[req.role, req.filter] = f"{CORE_REQUIREMENT}:{len(pools) + 1}"
    return pools
