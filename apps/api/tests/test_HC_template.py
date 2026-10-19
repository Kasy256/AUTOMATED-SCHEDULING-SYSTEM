import json
import re
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.industry_templates.schemas import load_packaged
from support import fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration

API = Path(__file__).resolve().parents[1]
VERSIONS = API / "migrations/versions"


def test_HC_template_loads_and_is_seeded(migrated_pg: PostgresContainer) -> None:
    packaged = load_packaged("healthcare").model_dump(mode="json")
    frozen = json.loads((VERSIONS / "0009_healthcare_v1.json").read_text(encoding="utf-8"))
    assert frozen == packaged
    [(definition,)] = fetch(
        superuser_url(migrated_pg),
        "SELECT definition FROM industry_template WHERE key = 'healthcare' AND version = 1",
    )
    assert definition == packaged


def test_HC_template_applies(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    response = client.post(
        "/api/v1/schedules/from-template",
        headers=admin.auth,
        json={
            "template_key": "healthcare",
            "name": "Ward roster",
            "timezone": "Africa/Kampala",
            "start_date": "2026-01-05",
            "end_date": "2026-02-01",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert set(created["resource_type_ids"]) == {"nurse", "clinical_officer", "lab_tech"}
    schedule_id = created["schedule"]["id"]
    slots = client.get(f"/api/v1/schedules/{schedule_id}/slot-templates", headers=admin.auth)
    assert len(slots.json()) == 1
    rules = client.get(f"/api/v1/schedules/{schedule_id}/constraints", headers=admin.auth).json()
    assert len(rules) == 12
    feasibility = client.get(f"/api/v1/schedules/{schedule_id}/feasibility", headers=admin.auth)
    assert feasibility.status_code == 200, feasibility.text


def _phase_sources() -> list[Path]:
    # The phase's own Python sources, against the Development merge-base (rule data lives in JSON).
    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=API, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            pytest.skip(f"git history unavailable: {done.stderr.strip()}")
        return done.stdout.strip()

    base = git("merge-base", "HEAD", "Development")
    root = Path(git("rev-parse", "--show-toplevel"))
    changed = git(
        "diff", "--name-only", "--diff-filter=AM", base, "--", "apps/api/src"
    ).splitlines()
    return [
        root / name
        for name in changed
        if name.endswith(".py") and "industry_templates/data/" not in name
    ]


def test_HC_template_has_no_magic_in_code() -> None:
    magic = re.compile(r"\b660\b|\b2400\b|\"Night\"")
    hits = [
        f"{path.name}:{n}"
        for path in _phase_sources()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if magic.search(line)
    ]
    assert hits == []
