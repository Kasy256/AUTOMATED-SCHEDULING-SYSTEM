from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from cartlyf_api.activities.schemas import (
    GENERATED_ATTRS,
    CoverageDemandSpec,
    RequirementSpec,
    SessionDemandSpec,
)
from cartlyf_api.schedules.schemas import Slot
from cartlyf_api.schedules.time_grid import Horizon, local_instant, week_windows
from cartlyf_engine.domain import AttrScalar


@dataclass(frozen=True)
class ActivityDraft:
    # Stable across regenerations: "<date>|<slot>" (coverage) or "<week Monday>#<n>" (session);
    # None for manual activities.
    key: str | None
    name: str
    duration_minutes: int
    candidate_starts: tuple[datetime, ...]
    requirements: tuple[RequirementSpec, ...]
    attrs: Mapping[str, AttrScalar]


# Matches the activity name column limit; the suffix (date, slot, week) is the part that matters.
MAX_NAME = 200


def _named(base: str, suffix: str) -> str:
    return base[: MAX_NAME - len(suffix)] + suffix


__all__ = ["GENERATED_ATTRS", "ActivityDraft", "ExpansionError", "expand_demand"]


class ExpansionError(ValueError):
    def __init__(self, loc: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.loc = loc


def _selected(labels: Sequence[str] | None, slots: Sequence[Slot]) -> list[Slot]:
    if labels is None:
        return list(slots)
    by_label = {s.label: s for s in slots}
    if unknown := [label for label in labels if label not in by_label]:
        raise ExpansionError(("spec", "slot_labels"), f"Unknown slot labels: {', '.join(unknown)}")
    return [by_label[label] for label in dict.fromkeys(labels)]


def _occurrences(slots: Sequence[Slot], horizon: Horizon) -> list[tuple[datetime, Slot, date]]:
    found = [
        (local_instant(day, slot.start_minute, horizon.timezone), slot, day)
        for day in horizon.days()
        for slot in slots
        if day.weekday() in slot.weekdays
    ]
    return sorted(found, key=lambda o: (o[0], o[1].label))


def expand_demand(
    name: str,
    spec: SessionDemandSpec | CoverageDemandSpec,
    slots: Sequence[Slot],
    horizon: Horizon,
) -> list[ActivityDraft]:
    selected = _selected(spec.slot_labels, slots)
    occurrences = _occurrences(selected, horizon)
    requirements = tuple(spec.requirements)
    if isinstance(spec, CoverageDemandSpec):
        return [
            ActivityDraft(
                f"{day.isoformat()}|{slot.label}",
                _named(name, f" {day.isoformat()} {slot.label}"),
                slot.duration_minutes,
                (start,),
                requirements,
                {**spec.attrs, "slot": slot.label, "weekday": day.isoweekday()},
            )
            for start, slot, day in occurrences
        ]
    durations = {s.duration_minutes for s in selected}
    if spec.duration_minutes is None and len(durations) > 1:
        raise ExpansionError(
            ("spec", "duration_minutes"),
            "The selected slots have different lengths; set duration_minutes",
        )
    duration = spec.duration_minutes or durations.pop()
    drafts: list[ActivityDraft] = []
    for week, (week_start, week_end) in enumerate(week_windows(horizon), start=1):
        starts = tuple(sorted({s for s, _, _ in occurrences if week_start <= s < week_end}))
        if not starts:
            continue
        local = week_start.astimezone(horizon.timezone).date()
        monday = local - timedelta(days=local.weekday())
        drafts += [
            ActivityDraft(
                f"{monday.isoformat()}#{n}",
                _named(name, f" W{week} #{n}"),
                duration,
                starts,
                requirements,
                spec.attrs,
            )
            for n in range(1, spec.sessions_per_week + 1)
        ]
    return drafts
