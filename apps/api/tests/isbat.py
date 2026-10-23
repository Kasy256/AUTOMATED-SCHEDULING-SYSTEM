"""ISBAT Term 1 built through the product: template -> CSV imports -> term split."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.industry_templates.schemas import IndustryTemplateDefinition, load_packaged
from support import Account, signup_and_confirm

FIXTURES = Path(__file__).resolve().parents[3] / "packages/engine/tests/fixtures/isbat/v1"
WEEK = {"start_date": "2026-01-12", "end_date": "2026-01-16", "timezone": "Africa/Kampala"}


@dataclass(frozen=True)
class BuiltTerm1:
    admin: Account
    schedule_id: str
    names: dict[str, str]  # id -> code or name, for renaming the snapshot


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _import(
    client: TestClient,
    admin: Account,
    job: dict[str, Any],
    name: str,
    mapping: object,
    content: str | None = None,
) -> None:
    created = client.post("/api/v1/imports", headers=admin.auth, json=job | {"filename": name})
    url = f"/api/v1/imports/{created.json()['id']}"
    client.put(
        f"{url}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=(read_fixture(name) if content is None else content).encode(),
    )
    dry = client.post(f"{url}/dry-run", headers=admin.auth, json={"mapping": mapping})
    assert dry.status_code == 200 and dry.json()["report"]["valid"], dry.text
    assert client.post(f"{url}/commit", headers=admin.auth).status_code == 200


def _resources(
    client: TestClient, admin: Account, type_id: UUID | str, name: str, **fields: object
) -> None:
    mapping = {"kind": "resources", "code": "code", "name": "name"} | fields
    _import(client, admin, {"kind": "resources", "resource_type_id": str(type_id)}, name, mapping)


def _demand_mapping(
    template: IndustryTemplateDefinition, applied: dict[str, Any]
) -> dict[str, Any]:
    shape = template.demand_shape
    assert shape is not None and shape.term_split is not None
    types = applied["resource_type_ids"]
    return {
        "kind": "demands",
        "demand_kind": shape.kind,
        "slot_template_id": applied["slot_template_ids"][shape.slot_template],
        "name": shape.name_column,
        "sessions_per_week": shape.sessions_per_week_column,
        "weekly_minutes": shape.weekly_minutes_column,
        "requirements": [
            {
                "role": r.role,
                "resource_type_id": types[r.resource_type_key],
                "count_min": r.count_min,
                "count_max": r.count_max,
                "count_from_fixed": r.count_from_fixed,
                "fixed_codes_column": r.fixed_codes_column,
                "tags_column": r.tags_column,
                "attribute_columns": r.attribute_columns,
            }
            for r in shape.requirements
        ],
        "term_split": shape.term_split.model_dump() | {"term": "Term 1"},
    }


def _hhmm(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def build_term1(client: TestClient, admin: Account | None = None) -> BuiltTerm1:
    app = client.app
    assert isinstance(app, FastAPI)
    admin = admin or signup_and_confirm(client, app)
    template = load_packaged("education")
    applied = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={"template_key": "education", "name": "ISBAT Term 1"} | WEEK,
    ).json()
    types = applied["resource_type_ids"]
    _resources(
        client,
        admin,
        types["lecturer"],
        "lecturers.csv",
        tags="subjects",
        attributes={"role": "role", "faculty": "faculty"},
    )
    _resources(
        client,
        admin,
        types["room"],
        "rooms.csv",
        capacity="capacity",
        tags="specialisations",
        attributes={"room_type": "room_type"},
    )
    _resources(
        client,
        admin,
        types["student_group"],
        "student_groups.csv",
        size="size",
        attributes={"program": "program", "semester": "semester"},
    )
    resources = client.get("/api/v1/resources", headers=admin.auth).json()
    by_code = {r["code"]: r["id"] for r in resources}
    for rule in csv.DictReader(io.StringIO(read_fixture("lecturer_availability.csv"))):
        response = client.post(
            f"/api/v1/resources/{by_code[rule['code']]}/availability-rules",
            headers=admin.auth,
            json={
                "kind": "available",
                "weekday": int(rule["weekday"]),
                "start_minute": _hhmm(rule["start"]),
                "end_minute": _hhmm(rule["end"]),
            },
        )
        assert response.status_code == 201, response.text
    schedule_id = applied["schedule"]["id"]
    _import(
        client,
        admin,
        {"kind": "demands", "schedule_id": schedule_id},
        "course_units.csv",
        _demand_mapping(template, applied),
    )

    base = f"/api/v1/schedules/{schedule_id}"
    demands = client.get(f"{base}/demands", headers=admin.auth).json()
    activities = client.get(f"{base}/activities", headers=admin.auth).json()
    constraints = client.get(f"{base}/constraints", headers=admin.auth).json()
    names = {r["id"]: r["code"] for r in resources}
    names |= {d["id"]: d["name"] for d in demands}
    names |= {a["id"]: a["name"] for a in activities}
    names |= {c["id"]: c["name"] for c in constraints}
    assert len(set(names.values())) == len(names), "renaming would merge two ids"
    return BuiltTerm1(admin, schedule_id, names)
