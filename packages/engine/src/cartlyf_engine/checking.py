"""What template checkers read: the placed assignments, indexed. Pure Python, no solver."""

from bisect import insort
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from cartlyf_engine.domain import Activity, Assignment, Problem
from cartlyf_engine.index import ProblemIndex


@dataclass(frozen=True)
class Finding:
    """One breach. Hard rule: every finding is a violation. Soft: penalty = weight x sum(amount)."""

    amount: int
    message: str
    activity_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()


class CheckContext:
    def __init__(
        self, problem: Problem, index: ProblemIndex, placed: Mapping[str, Assignment]
    ) -> None:
        self.problem = problem
        self.index = index
        self.placed: dict[str, Assignment] = {}
        self._holders: dict[str, frozenset[str]] = {}
        self._work: dict[str, list[Activity]] = defaultdict(list)
        for assignment in placed.values():
            self.place(assignment)

    def place(self, assignment: Assignment) -> None:
        activity_id = assignment.activity_id
        self.placed[activity_id] = assignment
        holders = frozenset(
            r for ids in assignment.resources.values() for r in ids if r in self.index.resources
        )
        self._holders[activity_id] = holders
        activity = self.index.activities[activity_id]
        for resource_id in holders:
            insort(self._work[resource_id], activity, key=self._order)

    def unplace(self, activity_id: str) -> None:
        del self.placed[activity_id]
        for resource_id in self._holders.pop(activity_id, frozenset()):
            self._work[resource_id] = [a for a in self._work[resource_id] if a.id != activity_id]

    def _order(self, activity: Activity) -> tuple[int, str]:
        return self.placed[activity.id].start, activity.id

    def holders(self, activity_id: str) -> frozenset[str]:
        return self._holders.get(activity_id, frozenset())

    def work(self, resource_id: str) -> list[Activity]:
        """Placed activities the resource works, by start then id."""
        return self._work.get(resource_id, [])
