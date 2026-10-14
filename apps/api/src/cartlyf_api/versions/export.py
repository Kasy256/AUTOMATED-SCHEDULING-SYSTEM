import csv
import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

HEADER = ["activity_id", "activity", "start", "end", "role", "resource_code", "resource"]
# Leading characters that spreadsheets would execute as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class ExportRow:
    activity_id: str
    activity: str
    start_at: datetime
    end_at: datetime
    role: str
    resource_code: str
    resource: str


def safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def _line(cells: list[str]) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(cells)
    return out.getvalue()


def csv_rows(rows: Iterable[ExportRow], tz: ZoneInfo) -> Iterator[str]:
    yield _line(HEADER)
    for r in sorted(rows, key=lambda r: (r.start_at, r.activity, r.role, r.resource_code)):
        yield _line(
            [
                safe_cell(c)
                for c in (
                    r.activity_id,
                    r.activity,
                    r.start_at.astimezone(tz).isoformat(),
                    r.end_at.astimezone(tz).isoformat(),
                    r.role,
                    r.resource_code,
                    r.resource,
                )
            ]
        )
