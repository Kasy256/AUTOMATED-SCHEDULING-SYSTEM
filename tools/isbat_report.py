"""EDU-06: compare our ISBAT Term 1 solution with the legacy published timetable (informational)."""

import argparse
import json
from pathlib import Path

from cartlyf_engine.domain import Problem, SolveOptions
from cartlyf_engine.solve import solve
from tools.metrics import (
    Placement,
    from_legacy_csv,
    from_solution,
    idle_minutes,
    lecturer_load_spread,
    room_fit,
    weekday_spread,
)

REPO = Path(__file__).resolve().parents[1]
PROBLEM = REPO / "packages/engine/tests/fixtures/isbat/v1/term1_problem.json"
LEGACY = REPO / "ISBAT-TIMETABLE-BACKEND/TIMETABLE_TERM1_COMPLETE.csv"
OUT = REPO / "docs/benchmarks/isbat_term1.md"


def _row(name: str, ours: str, legacy: str) -> str:
    return f"| {name} | {ours} | {legacy} |"


def _metrics(placements: list[Placement]) -> list[str]:
    low, high, stdev = lecturer_load_spread(placements)
    utilisation, over = room_fit(placements)
    groups = {g for p in placements for g in p.group_ids}
    lecturers = {p.lecturer_id for p in placements}
    return [
        f"{len(placements)} sessions, {len(groups)} groups, {len(lecturers)} lecturers",
        f"{idle_minutes(placements)} min ({idle_minutes(placements) / len(groups):.0f} per group)",
        f"{low} to {high} sessions, stdev {stdev:.2f}",
        f"{utilisation:.0f}% seats used; {over} over capacity",
        f"{weekday_spread(placements):.2f}",
    ]


def build_report(time_limit_s: int, workers: int) -> str:
    problem = Problem.model_validate(json.loads(PROBLEM.read_text(encoding="utf-8")))
    solution = solve(problem, SolveOptions(time_limit_s=time_limit_s, seed=0, num_workers=workers))
    ours = _metrics(from_solution(problem, solution))
    legacy = _metrics(from_legacy_csv(LEGACY))
    names = [
        "Size",
        "Student idle time (gaps between a group's sessions in a day)",
        "Lecturer load spread (sessions per teaching lecturer)",
        "Room fit (headcount / capacity)",
        "Weekday spread (mean stdev of a group's sessions per day; 0 = even)",
    ]
    terms = "\n".join(f"| {t.constraint_id} | {t.penalty} |" for t in solution.score.terms)
    return "\n".join(
        [
            "# ISBAT Term 1 — Cartlyf vs legacy timetable (EDU-06)",
            "",
            "> **Not a like-for-like comparison.** Our side is the legacy *seed* data (Computing",
            "> faculty: BSCAIT + BCS, 12 groups, 23 lecturers, 37 rooms), split to Term 1 and",
            "> merged by canonical subject. `TIMETABLE_TERM1_COMPLETE.csv` is a different dataset:",
            "> mostly Business programmes (BBA, BSC.AF) with other lecturer ids and 115-minute",
            "> periods. Each metric is computed on each timetable on its own (decision D2,",
            "> 2026-10-12). Informational, not a gate.",
            "",
            "| Metric | Cartlyf (seed data) | Legacy CSV |",
            "|---|---|---|",
            *(_row(n, o, g) for n, o, g in zip(names, ours, legacy, strict=True)),
            "",
            "## Our run",
            "",
            f"- Solver: status **{solution.status}**, hard violations (checker) "
            f"**{solution.score.hard_violations}**, soft total {solution.score.soft_total}",
            f"- Wall time {solution.stats.wall_time_s:.1f} s; limit {time_limit_s} s, "
            f"{workers} workers, seed 0",
            f"- Problem: `{PROBLEM.relative_to(REPO).as_posix()}`",
            "  (one teaching week, 120-minute periods)",
            "",
            "| Soft rule | Penalty |",
            "|---|---|",
            terms,
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-limit", type=int, default=60)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_report(args.time_limit, args.workers), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
