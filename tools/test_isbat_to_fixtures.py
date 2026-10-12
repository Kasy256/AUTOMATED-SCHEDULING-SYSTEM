import csv
import json
import sys
from pathlib import Path

from tools.isbat_to_fixtures import load_legacy, write_fixtures

REPO = Path(__file__).resolve().parents[1]
LEGACY = REPO / "ISBAT-TIMETABLE-BACKEND"
FIXTURES = REPO / "packages/engine/tests/fixtures/isbat/v1"
GENERATED = [
    "lecturers.csv",
    "lecturer_availability.csv",
    "rooms.csv",
    "student_groups.csv",
    "course_units.csv",
    "source.json",
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_EDU_01_parses_legacy_without_importing_it() -> None:
    legacy = load_legacy(LEGACY)
    counts = (len(legacy.lecturers), len(legacy.rooms), len(legacy.programs), len(legacy.courses))
    assert counts == (23, 37, 12, 73)
    legacy_modules = ("app.", "pymongo", "seed_", "dotenv")
    assert "app" not in sys.modules
    assert not any(name.startswith(legacy_modules) for name in sys.modules)


def test_EDU_01_committed_fixtures_match_a_fresh_run(tmp_path: Path) -> None:
    write_fixtures(load_legacy(LEGACY), tmp_path)
    for name in GENERATED:
        fresh = (tmp_path / name).read_text(encoding="utf-8")
        committed = (FIXTURES / name).read_text(encoding="utf-8")
        assert fresh == committed, f"{name} is stale: rerun tools/isbat_to_fixtures.py"


def test_EDU_01_course_units_carry_subject_pair_and_minutes(tmp_path: Path) -> None:
    write_fixtures(load_legacy(LEGACY), tmp_path)
    units = rows(tmp_path / "course_units.csv")
    by_key = {(r["group"], r["unit"]): r for r in units}
    practical = by_key[("SG_BSCAIT_126_S1", "BIT1107")]
    assert {k: v for k, v in practical.items() if k != "unit_name"} == {
        "group": "SG_BSCAIT_126_S1",
        "unit": "BIT1107",
        "subject": "PROG_C",
        "pair": "BIT1103_GROUP",
        "term": "Term 1",
        "room_type": "Lab",
        "weekly_minutes": "240",
    }
    assert len({r["unit"] for r in units}) == 73
    assert {r["group"] for r in units} == {g["code"] for g in rows(tmp_path / "student_groups.csv")}


def test_EDU_01_part_timers_have_availability(tmp_path: Path) -> None:
    write_fixtures(load_legacy(LEGACY), tmp_path)
    lecturers = {r["code"]: r for r in rows(tmp_path / "lecturers.csv")}
    assert lecturers["L003"]["role"] == "Part-Time"
    assert lecturers["L005"]["subjects"].split(";")[0] == "COMP_HARDWARE_OS"
    windows = [r for r in rows(tmp_path / "lecturer_availability.csv") if r["code"] == "L003"]
    assert {"code": "L003", "weekday": "1", "start": "09:00", "end": "11:00"} in windows
    assert len(windows) == 5


def test_EDU_01_source_records_versions_and_hashes(tmp_path: Path) -> None:
    write_fixtures(load_legacy(LEGACY), tmp_path)
    source = json.loads((tmp_path / "source.json").read_text(encoding="utf-8"))
    assert source["fixture_version"] == 1
    assert "seed_courses_data.py" in source["sources"]
    assert source["counts"]["groups"] == 12
