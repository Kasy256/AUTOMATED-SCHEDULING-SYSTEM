"""Timetable quality metrics for the EDU-06 comparison, over a neutral session shape."""

import csv
import itertools
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from cartlyf_engine.domain import Problem, Solution

DAY_MINUTES = 1440
LEGACY_DAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4}
TEACHING_DAYS = 5


@dataclass(frozen=True)
class Placement:
    group_ids: tuple[str, ...]
    lecturer_id: str
    room_capacity: int
    headcount: int
    weekday: int
    start_minute: int
    end_minute: int


def idle_minutes(placements: list[Placement]) -> int:
    """Total gap between consecutive sessions of each group on each day."""
    by_group_day: dict[tuple[str, int], list[Placement]] = defaultdict(list)
    for p in placements:
        for group in p.group_ids:
            by_group_day[(group, p.weekday)].append(p)
    total = 0
    for sessions in by_group_day.values():
        ordered = sorted(sessions, key=lambda s: s.start_minute)
        total += sum(max(0, b.start_minute - a.end_minute) for a, b in itertools.pairwise(ordered))
    return total


def lecturer_load_spread(placements: list[Placement]) -> tuple[int, int, float]:
    """Min, max and population stdev of sessions per teaching lecturer."""
    loads = list(Counter(p.lecturer_id for p in placements).values())
    return min(loads), max(loads), statistics.pstdev(loads)


def room_fit(placements: list[Placement]) -> tuple[float, int]:
    """Mean seat utilisation (%) and how many sessions exceed their room's capacity."""
    utilisation = [100 * p.headcount / p.room_capacity for p in placements]
    over = sum(1 for p in placements if p.headcount > p.room_capacity)
    return statistics.fmean(utilisation), over


def weekday_spread(placements: list[Placement]) -> float:
    """Mean over groups of the stdev of their sessions per teaching day (0 = perfectly even)."""
    per_group: dict[str, Counter[int]] = defaultdict(Counter)
    for p in placements:
        for group in p.group_ids:
            per_group[group][p.weekday] += 1
    spreads = [
        statistics.pstdev([days[d] for d in range(TEACHING_DAYS)]) for days in per_group.values()
    ]
    return statistics.fmean(spreads)


def _minutes(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def from_legacy_csv(path: Path) -> list[Placement]:
    """Rows sharing a `VAR_<n>` session id are one session taught to several groups."""
    sessions: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sessions["_".join(row["Session_ID"].split("_")[:2])].append(row)
    placements: list[Placement] = []
    for rows in sessions.values():
        first = rows[0]
        placements.append(
            Placement(
                group_ids=tuple(r["Student_Group"] for r in rows),
                lecturer_id=first["Lecturer_ID"],
                room_capacity=int(first["Room_Capacity"]),
                headcount=sum(int(r["Group_Size"]) for r in rows),
                weekday=LEGACY_DAYS[first["Day"]],
                start_minute=_minutes(first["Start_Time"]),
                end_minute=_minutes(first["End_Time"]),
            )
        )
    return placements


def from_solution(problem: Problem, solution: Solution) -> list[Placement]:
    """Assumes a horizon starting on a Monday at local midnight (as the benchmark week does)."""
    resources = {r.id: r for r in problem.resources}
    activities = {a.id: a for a in problem.activities}
    placements: list[Placement] = []
    for a in solution.assignments:
        groups = a.resources.get("group", ())
        [room] = a.resources["room"]
        [lecturer] = a.resources["lecturer"]
        duration = activities[a.activity_id].duration
        placements.append(
            Placement(
                group_ids=tuple(groups),
                lecturer_id=lecturer,
                room_capacity=resources[room].capacity or 0,
                headcount=sum(resources[g].size or 0 for g in groups),
                weekday=a.start // DAY_MINUTES,
                start_minute=a.start % DAY_MINUTES,
                end_minute=a.start % DAY_MINUTES + duration,
            )
        )
    return placements
