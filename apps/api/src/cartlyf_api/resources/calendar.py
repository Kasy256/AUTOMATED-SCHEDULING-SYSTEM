from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from cartlyf_api.schedules.time_grid import Horizon, Interval, local_instant

AvailabilityKind = Literal["available", "unavailable", "preferred", "avoided"]


@dataclass(frozen=True)
class WeeklyRule:
    kind: AvailabilityKind
    weekday: int  # 0 = Monday
    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class DatedException:
    kind: AvailabilityKind
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class CalendarWindows:
    unavailable: list[Interval]
    preferred: list[Interval]
    avoided: list[Interval]


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(i for i in intervals if i[1] > i[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def subtract(base: Iterable[Interval], cut: Iterable[Interval]) -> list[Interval]:
    result: list[Interval] = []
    cuts = merge(cut)
    for start, end in merge(base):
        for cut_start, cut_end in cuts:
            if cut_end <= start or cut_start >= end:
                continue
            if cut_start > start:
                result.append((start, cut_start))
            start = max(start, cut_end)
            if start >= end:
                break
        if start < end:
            result.append((start, end))
    return result


def clip(intervals: Iterable[Interval], start: datetime, end: datetime) -> list[Interval]:
    return merge((max(s, start), min(e, end)) for s, e in intervals)


def expand_calendar(
    rules: Sequence[WeeklyRule], exceptions: Sequence[DatedException], horizon: Horizon
) -> CalendarWindows:
    """Concrete UTC windows for the horizon. Any `available` rule makes the resource
    unavailable outside its available windows; exceptions are applied last."""
    tz = horizon.timezone

    def weekly(kind: AvailabilityKind) -> list[Interval]:
        return [
            (local_instant(day, r.start_minute, tz), local_instant(day, r.end_minute, tz))
            for day in horizon.days()
            for r in rules
            if r.kind == kind and r.weekday == day.weekday()
        ]

    def dated(kind: AvailabilityKind) -> list[Interval]:
        return [(e.starts_at, e.ends_at) for e in exceptions if e.kind == kind]

    span = [(horizon.start, horizon.end)]
    blocked = weekly("unavailable")
    if any(r.kind == "available" for r in rules):
        blocked += subtract(span, weekly("available"))
    unavailable = subtract(blocked + dated("unavailable"), dated("available"))
    return CalendarWindows(
        unavailable=clip(unavailable, horizon.start, horizon.end),
        preferred=clip(weekly("preferred") + dated("preferred"), horizon.start, horizon.end),
        avoided=clip(weekly("avoided") + dated("avoided"), horizon.start, horizon.end),
    )
