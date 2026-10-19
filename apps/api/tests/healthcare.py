"""Seeded 40-staff, 4-week healthcare roster built through the product."""

import csv
import io
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from isbat import _import  # pyright: ignore[reportPrivateUsage]

from support import Account, signup_and_confirm

START = date(2027, 1, 4)
HORIZON = {"start_date": "2027-01-04", "end_date": "2027-01-31", "timezone": "Africa/Kampala"}
CONTRACT_MINUTES = 2400
WARDS = ("A", "B")
FIRST = (
    "Amina",
    "Brian",
    "Cecilia",
    "David",
    "Esther",
    "Felix",
    "Grace",
    "Hassan",
    "Irene",
    "Joel",
)
LAST = ("Akello", "Byaruhanga", "Chebet", "Dungu", "Ekirapa", "Friday", "Gumisiriza", "Hakim")
GRADES = ("Junior", "Senior", "Lead")
HEADER = ["code", "name", "type", "tags", "contract_minutes_per_week", "grade"]
# (resource type key, tag, headcount)
STAFF = (("nurse", "RN", 24), ("nurse", "midwife", 11), ("lab_tech", "", 5))


@dataclass(frozen=True)
class BuiltRoster:
    admin: Account
    schedule_id: str
    names: dict[str, str]  # id -> code or name, for renaming the snapshot


def staff_csv(seed: int) -> str:
    rng = random.Random(seed)
    people = [(f, last) for f in FIRST for last in LAST]
    rng.shuffle(people)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    n = 0
    for type_key, tag, count in STAFF:
        for _ in range(count):
            first, last = people[n]
            n += 1
            grade = rng.choice(GRADES)
            writer.writerow(
                [f"S{n:02d}", f"{first} {last}", type_key, tag, CONTRACT_MINUTES, grade]
            )
    return out.getvalue()


def leave(seed: int) -> list[tuple[str, date, date]]:
    rng = random.Random(f"leave-{seed}")
    codes = sorted(rng.sample([f"S{n:02d}" for n in range(1, 41)], 3))
    spans: list[tuple[str, date, date]] = []
    for code in codes:
        first = START + timedelta(days=rng.randrange(0, 24))
        spans.append((code, first, first + timedelta(days=rng.randint(1, 3))))
    return spans


def _rows_of(type_key: str, text: str) -> str:
    rows = list(csv.DictReader(io.StringIO(text)))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(r for r in rows if r["type"] == type_key)
    return out.getvalue()


def _requirement(role: str, type_id: str, count: int, tag: str | None) -> dict[str, Any]:
    return {
        "role": role,
        "resource_type_id": type_id,
        "count_min": count,
        "count_max": count,
        "hard": False,
        "weight": 1000,
        "tags": [tag] if tag else [],
    }


def _demand(
    client: TestClient, admin: Account, base: str, name: str, slots: str, spec: dict[str, Any]
) -> None:
    response = client.post(
        f"{base}/demands",
        headers=admin.auth,
        json={"name": name, "slot_template_id": slots, "spec": spec},
    )
    assert response.status_code == 201, response.text


def build_roster(client: TestClient, seed: int = 8) -> BuiltRoster:
    app = client.app
    assert isinstance(app, FastAPI)
    admin = signup_and_confirm(client, app)
    applied = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={"template_key": "healthcare", "name": "Ward roster"} | HORIZON,
    ).json()
    types = applied["resource_type_ids"]
    text = staff_csv(seed)
    mapping = {
        "kind": "resources",
        "code": "code",
        "name": "name",
        "tags": "tags",
        "attributes": {
            "contract_minutes_per_week": "contract_minutes_per_week",
            "grade": "grade",
        },
    }
    for type_key in ("nurse", "lab_tech"):
        _import(
            client,
            admin,
            {"kind": "resources", "resource_type_id": str(types[type_key])},
            f"{type_key}.csv",
            mapping,
            content=_rows_of(type_key, text),
        )
    resources = client.get("/api/v1/resources", headers=admin.auth).json()
    by_code = {r["code"]: r["id"] for r in resources}
    for code, first, last in leave(seed):
        response = client.post(
            f"/api/v1/resources/{by_code[code]}/availability-exceptions",
            headers=admin.auth,
            json={
                "kind": "unavailable",
                "starts_at": f"{first.isoformat()}T00:00:00+03:00",
                "ends_at": f"{(last + timedelta(days=1)).isoformat()}T00:00:00+03:00",
                "reason": "Leave",
            },
        )
        assert response.status_code == 201, response.text

    schedule_id = applied["schedule"]["id"]
    slots = applied["slot_template_ids"]["Shifts"]
    base = f"/api/v1/schedules/{schedule_id}"
    for ward in WARDS:
        for name, labels, rn in (
            (f"Ward {ward} Day", ["Day"], 3),
            (f"Ward {ward} Evening and night", ["Evening", "Night"], 2),
        ):
            spec = {
                "kind": "coverage",
                "slot_labels": labels,
                "requirements": [
                    _requirement("rn", types["nurse"], rn, "RN"),
                    _requirement("midwife", types["nurse"], 1, "midwife"),
                ],
                "attrs": {"ward": ward},
            }
            _demand(client, admin, base, name, slots, spec)
    lab = {
        "kind": "coverage",
        "requirements": [_requirement("lab_tech", types["lab_tech"], 1, None)],
    }
    _demand(client, admin, base, "Lab cover", slots, lab)

    demands = client.get(f"{base}/demands", headers=admin.auth).json()
    activities = client.get(f"{base}/activities", headers=admin.auth).json()
    constraints = client.get(f"{base}/constraints", headers=admin.auth).json()
    names = {r["id"]: r["code"] for r in resources}
    names |= {d["id"]: d["name"] for d in demands}
    names |= {a["id"]: a["name"] for a in activities}
    names |= {c["id"]: c["name"] for c in constraints}
    assert len(set(names.values())) == len(names), "renaming would merge two ids"
    return BuiltRoster(admin, schedule_id, names)
