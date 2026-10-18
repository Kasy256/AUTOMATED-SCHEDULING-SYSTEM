"""Reports on one version, from its problem snapshot and its assignments in minutes."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from cartlyf_api.versions.schemas import (
    CoverageGap,
    FairnessSpread,
    PersonLoad,
    ResourceUtilisation,
    VersionReport,
)
from cartlyf_engine.domain import Assignment, Problem

Interval = tuple[int, int]


def _union(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersect(a: list[Interval], b: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        start, end = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if start < end:
            out.append((start, end))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _subtract(a: list[Interval], b: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for start, end in a:
        cursor = start
        for b_start, b_end in b:
            if b_end <= cursor or b_start >= end:
                continue
            if b_start > cursor:
                out.append((cursor, b_start))
            cursor = max(cursor, b_end)
        if cursor < end:
            out.append((cursor, end))
    return out


def _length(intervals: Iterable[Interval]) -> int:
    return sum(end - start for start, end in intervals)


def build_report(
    version_id: UUID,
    problem: Problem,
    assignments: Mapping[str, Assignment],
    origin: datetime,
    tz: ZoneInfo,
) -> VersionReport:
    durations = {a.id: a.duration for a in problem.activities}
    requirements = {a.id: a.requirements for a in problem.activities}
    # The timetable's slot grid: wherever any activity could start, for as long as it runs.
    schedulable = _union(
        (s, s + a.duration) for a in problem.activities for s in a.candidate_starts
    )

    held: dict[str, list[Interval]] = defaultdict(list)
    gaps: list[CoverageGap] = []
    for assignment in assignments.values():
        duration = durations.get(assignment.activity_id)
        if duration is None:
            continue
        interval = (assignment.start, assignment.start + duration)
        for rid in {r for ids in assignment.resources.values() for r in ids}:
            held[rid].append(interval)
        for req in requirements[assignment.activity_id]:
            count = len(assignment.resources.get(req.role, ()))
            if count < req.count_min:
                gaps.append(
                    CoverageGap(
                        activity_id=UUID(assignment.activity_id),
                        role=req.role,
                        required_min=req.count_min,
                        assigned=count,
                    )
                )

    utilisation: list[ResourceUtilisation] = []
    load: list[PersonLoad] = []
    minutes_by_type: dict[str, list[int]] = defaultdict(list)
    for resource in problem.resources:
        intervals = held.get(resource.id, [])
        available = _subtract(schedulable, _union((w.start, w.end) for w in resource.unavailable))
        available_minutes = _length(available)
        assigned_minutes = _length(_intersect(_union(intervals), available))
        utilisation.append(
            ResourceUtilisation(
                resource_id=UUID(resource.id),
                type_key=resource.type_key,
                assigned_minutes=assigned_minutes,
                available_minutes=available_minutes,
                ratio=round(assigned_minutes / available_minutes, 3) if available_minutes else 0.0,
            )
        )
        minutes = _length(intervals)
        minutes_by_type[resource.type_key].append(minutes)
        if resource.kind == "person":
            per_day: dict[date, int] = defaultdict(int)
            for start, end in intervals:
                local = (origin + timedelta(minutes=start)).astimezone(tz).date()
                per_day[local] += end - start
            busiest = min(per_day, key=lambda d: (-per_day[d], d)) if per_day else None
            load.append(
                PersonLoad(
                    resource_id=UUID(resource.id),
                    activities=len(intervals),
                    minutes=minutes,
                    busiest_day=busiest,
                    busiest_day_minutes=per_day[busiest] if busiest else 0,
                )
            )

    fairness = [
        FairnessSpread(
            type_key=type_key,
            resources=len(values),
            min_minutes=min(values),
            max_minutes=max(values),
            mean_minutes=round(sum(values) / len(values), 1),
            spread=max(values) - min(values),
        )
        for type_key, values in sorted(minutes_by_type.items())
    ]
    return VersionReport(
        version_id=version_id,
        utilisation=utilisation,
        load=load,
        coverage_gaps=gaps,
        fairness=fairness,
    )
