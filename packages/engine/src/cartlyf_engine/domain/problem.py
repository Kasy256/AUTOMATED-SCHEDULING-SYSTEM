import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from typing import Self

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from cartlyf_engine.domain.activities import Activity
from cartlyf_engine.domain.base import Frozen, Id, Key
from cartlyf_engine.domain.constraints import ConstraintInstance
from cartlyf_engine.domain.resources import Resource
from cartlyf_engine.domain.solution import Assignment
from cartlyf_engine.domain.time import Window


class SolveOptions(Frozen):
    time_limit_s: PositiveInt = 60
    seed: NonNegativeInt = 0
    num_workers: PositiveInt = 8


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


class Problem(Frozen):
    horizon_minutes: PositiveInt
    day_windows: tuple[Window, ...]
    week_windows: tuple[Window, ...]
    named_windows: dict[Key, tuple[Window, ...]] = Field(default_factory=dict)
    resources: tuple[Resource, ...]
    activities: tuple[Activity, ...]
    constraints: tuple[ConstraintInstance, ...] = ()
    baseline: tuple[Assignment, ...] | None = None
    history: dict[Id, dict[Key, NonNegativeInt]] | None = None
    options: SolveOptions = SolveOptions()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for kind, items in (
            ("resource", self.resources),
            ("activity", self.activities),
            ("constraint", self.constraints),
        ):
            if dupes := _duplicates(item.id for item in items):
                raise ValueError(f"duplicate {kind} ids: {dupes}")
        windows = [*self.day_windows, *self.week_windows]
        windows += [w for ws in self.named_windows.values() for w in ws]
        windows += [w for r in self.resources for w in (*r.unavailable, *r.preferred, *r.avoided)]
        if any(w.end > self.horizon_minutes for w in windows):
            raise ValueError("a window ends after the horizon")
        resource_ids = {r.id for r in self.resources}
        for activity in self.activities:
            if activity.candidate_starts[-1] + activity.duration > self.horizon_minutes:
                raise ValueError(f"activity {activity.id} ends after the horizon")
            referenced = {i for r in activity.requirements for i in r.fixed_resource_ids}
            if activity.pinned is not None:
                referenced |= {i for ids in activity.pinned.resources.values() for i in ids}
            if unknown := referenced - resource_ids:
                raise ValueError(
                    f"activity {activity.id} names unknown resource ids {sorted(unknown)}"
                )
        return self


def problem_hash(problem: Problem) -> str:
    """SHA-256 of the canonical JSON of the problem data; solve options are not part of it."""
    data = problem.model_dump(mode="json", exclude={"options"})
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
