import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tools.seed_demo import seed

pytestmark = pytest.mark.integration


def test_seed_creates_demo_orgs_once(client: TestClient, app: FastAPI, tmp_path: Path) -> None:
    out = tmp_path / "accounts.json"
    created = seed(client, out, load_orgs=1)
    assert created == ["isbat", "healthcare", "load-1"]
    accounts = json.loads(out.read_text())
    assert sorted(accounts) == ["healthcare", "isbat", "load-1"]

    for label, account in accounts.items():
        login = client.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": account["password"]}
        )
        assert login.status_code == 200, label
        token = login.json()["access_token"]
        schedules = client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert len(schedules.json()) == 1, label
        assert account["schedule_id"] == schedules.json()[0]["id"]

    assert seed(client, out, load_orgs=1) == []
    assert json.loads(out.read_text()) == accounts
