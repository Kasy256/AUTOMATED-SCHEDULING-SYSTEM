from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

Placed = tuple[datetime, Mapping[str, frozenset[UUID]]]


@dataclass(frozen=True)
class DiffResult:
    added: list[UUID]
    removed: list[UUID]
    moved: list[UUID]
    reassigned: list[UUID]


def diff(before: Mapping[UUID, Placed], after: Mapping[UUID, Placed]) -> DiffResult:
    """An activity whose start and resources both changed is reported as moved only."""
    moved: list[UUID] = []
    reassigned: list[UUID] = []
    for activity_id in before.keys() & after.keys():
        old, new = before[activity_id], after[activity_id]
        if old[0] != new[0]:
            moved.append(activity_id)
        elif _normalised(old[1]) != _normalised(new[1]):
            reassigned.append(activity_id)
    return DiffResult(
        added=sorted(after.keys() - before.keys(), key=str),
        removed=sorted(before.keys() - after.keys(), key=str),
        moved=sorted(moved, key=str),
        reassigned=sorted(reassigned, key=str),
    )


def _normalised(resources: Mapping[str, frozenset[UUID]]) -> dict[str, frozenset[UUID]]:
    return {role: ids for role, ids in resources.items() if ids}
