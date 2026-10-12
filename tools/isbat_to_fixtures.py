"""One-off: legacy ISBAT seed modules -> CSV fixtures. Never imported by the product.

The seed modules connect to MongoDB or import `app.*`, so they are parsed with `ast` and only
their pure data functions run, in an empty namespace.
"""

import argparse
import ast
import csv
import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY = REPO / "ISBAT-TIMETABLE-BACKEND"
DEFAULT_OUT = REPO / "packages/engine/tests/fixtures/isbat/v1"
FIXTURE_VERSION = 1
WEEKDAYS = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5}

# Any: legacy records are untyped dicts straight out of the seed modules.
Record = dict[str, Any]

LECTURERS = "seed_lecturers_data.py"
ROOMS = "seed_rooms_data.py"
PROGRAMS = "seed_programs_data.py"
COURSES = "seed_courses_data.py"
CANONICAL = "app/services/canonical_courses.py"
CONFIG = "seed_config_data.py"


@dataclass(frozen=True)
class Legacy:
    lecturers: list[Record]
    rooms: list[Record]
    programs: list[Record]
    courses: list[Record]
    canonical: dict[str, list[str]]
    time_slots: list[Record]
    sources: dict[str, str]


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call(path: Path, function: str) -> list[Record]:
    node = next(
        n for n in _tree(path).body if isinstance(n, ast.FunctionDef) and n.name == function
    )
    namespace: dict[str, Any] = {"List": list, "Dict": dict}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return cast(list[Record], namespace[function]())


def _constant(path: Path, name: str) -> Any:
    for node in _tree(path).body:
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign):
            target, value = node.targets[0], node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return ast.literal_eval(value)
    raise LookupError(f"{name} not found in {path}")


def load_legacy(root: Path) -> Legacy:
    files = [LECTURERS, ROOMS, PROGRAMS, COURSES, CANONICAL, CONFIG]
    return Legacy(
        lecturers=_call(root / LECTURERS, "get_all_lecturers"),
        rooms=_call(root / ROOMS, "get_all_rooms"),
        programs=_call(root / PROGRAMS, "get_all_programs"),
        courses=_call(root / COURSES, "get_all_courses"),
        canonical=_constant(root / CANONICAL, "FALLBACK_CANONICAL_COURSE_MAPPING"),
        time_slots=_constant(root / CONFIG, "DEFAULT_TIME_SLOTS"),
        sources={f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files},
    )


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _course_unit_rows(legacy: Legacy) -> list[list[object]]:
    courses = {c["id"]: c for c in legacy.courses}
    subject_of = {code: cid for cid, codes in legacy.canonical.items() for code in codes}
    rows: list[list[object]] = []
    for program in legacy.programs:
        for entry in program["course_units"]:
            course = courses[entry["code"]]
            if course["id"] not in subject_of:
                raise LookupError(f"{course['id']} has no canonical subject")
            rows.append(
                [
                    program["id"],
                    course["id"],
                    course["name"],
                    subject_of[course["id"]],
                    course["course_group"] or "",
                    course["preferred_term"],
                    course["preferred_room_type"],
                    course["weekly_hours"] * 60,
                ]
            )
    return rows


def _availability_rows(legacy: Legacy) -> list[list[object]]:
    rows: list[list[object]] = []
    for lecturer in legacy.lecturers:
        availability = cast(dict[str, list[str]], lecturer.get("availability") or {})
        for day, windows in availability.items():
            rows.extend([lecturer["id"], WEEKDAYS[day], *w.split("-")] for w in windows)
    return rows


def write_fixtures(legacy: Legacy, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "lecturers.csv",
        ["code", "name", "role", "faculty", "subjects"],
        (
            [x["id"], x["name"], x["role"], x["faculty"], ";".join(x["specializations"])]
            for x in legacy.lecturers
        ),
    )
    _write_csv(
        out / "lecturer_availability.csv",
        ["code", "weekday", "start", "end"],
        _availability_rows(legacy),
    )
    _write_csv(
        out / "rooms.csv",
        ["code", "name", "room_type", "capacity", "specialisations"],
        (
            [
                r["id"],
                r["room_number"],
                r["room_type"],
                r["capacity"],
                ";".join(r["specializations"]),
            ]
            for r in legacy.rooms
        ),
    )
    _write_csv(
        out / "student_groups.csv",
        ["code", "name", "program", "semester", "size"],
        (
            [p["id"], f"{p['batch']} {p['semester']}", p["program"], p["semester"], p["size"]]
            for p in legacy.programs
        ),
    )
    units = _course_unit_rows(legacy)
    _write_csv(
        out / "course_units.csv",
        ["group", "unit", "unit_name", "subject", "pair", "term", "room_type", "weekly_minutes"],
        units,
    )
    source = {
        "fixture_version": FIXTURE_VERSION,
        "sources": legacy.sources,
        "counts": {
            "lecturers": len(legacy.lecturers),
            "rooms": len(legacy.rooms),
            "groups": len(legacy.programs),
            "units": len(legacy.courses),
            "course_unit_rows": len(units),
        },
    }
    text = json.dumps(source, indent=2, sort_keys=True) + "\n"
    (out / "source.json").write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    write_fixtures(load_legacy(args.legacy), args.out)


if __name__ == "__main__":
    main()
