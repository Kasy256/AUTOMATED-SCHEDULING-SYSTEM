"""What template checkers read: the placed assignments, indexed. Pure Python, no solver."""

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
        self.placed = placed
        self._holders: dict[str, frozenset[str]] = {}
        work: dict[str, list[Activity]] = defaultdict(list)
        for activity_id, assignment in placed.items():
            holders = frozenset(
                r for ids in assignment.resources.values() for r in ids if r in index.resources
            )
            self._holders[activity_id] = holders
            for resource_id in holders:
                work[resource_id].append(index.activities[activity_id])
        self._work = {
            r: sorted(acts, key=lambda a: (placed[a.id].start, a.id)) for r, acts in work.items()
        }

    def holders(self, activity_id: str) -> frozenset[str]:
        return self._holders.get(activity_id, frozenset())

    def work(self, resource_id: str) -> list[Activity]:
        """Placed activities the resource works, by start then id."""
        return self._work.get(resource_id, [])
