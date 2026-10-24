"""Seed demo organisations (ISBAT Term 1, the healthcare roster, load-test copies) into an
environment, through the product itself:

    uv run --env-file .env.staging python tools/seed_demo.py <accounts.json> [load-orgs]

The env file points at the target database (as cartlyf_app) and object storage. The API runs
in-process with console email, so confirmation links are read in memory and never sent.
Accounts that already log in are skipped. Keep <accounts.json> out of the repo: it holds passwords.
"""

import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api/tests")]

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from healthcare import build_roster  # noqa: E402
from isbat import build_term1  # noqa: E402

from cartlyf_api.main import create_app  # noqa: E402
from cartlyf_api.settings import load_settings  # noqa: E402
from support import Account, signup_and_confirm  # noqa: E402

ORG_NAMES = {"isbat": "ISBAT University (demo)", "healthcare": "Kampala General (demo)"}


def _logs_in(client: TestClient, account: dict[str, str]) -> bool:
    body = {"email": account["email"], "password": account["password"]}
    return client.post("/api/v1/auth/login", json=body).status_code == 200


def _create(client: TestClient, label: str) -> dict[str, str]:
    app = client.app
    assert isinstance(app, FastAPI)
    password = secrets.token_urlsafe(18)
    org = ORG_NAMES.get(label, f"Load test {label}")
    admin: Account = signup_and_confirm(client, app, org_name=org, password=password)
    built = (
        build_roster(client, admin=admin) if label == "healthcare" else build_term1(client, admin)
    )
    return {"email": admin.email, "password": password, "schedule_id": built.schedule_id}


def seed(client: TestClient, credentials_out: Path, load_orgs: int) -> list[str]:
    """Create every missing demo organisation; returns the labels created."""
    accounts: dict[str, dict[str, str]] = (
        json.loads(credentials_out.read_text()) if credentials_out.exists() else {}
    )
    created: list[str] = []
    for label in ["isbat", "healthcare", *(f"load-{n}" for n in range(1, load_orgs + 1))]:
        existing = accounts.get(label)
        if existing and _logs_in(client, existing):
            continue
        accounts[label] = _create(client, label)
        credentials_out.write_text(json.dumps(accounts, indent=2))
        created.append(label)
    return created


def main(argv: list[str]) -> None:
    # In-process only: console email keeps links in memory; the limit guards nothing here.
    settings = load_settings().model_copy(
        update={
            "environment": "local",
            "email_provider": "console",
            "auth_rate_limit_per_minute": 1000,
        }
    )
    with TestClient(create_app(settings), raise_server_exceptions=True) as client:
        created = seed(client, Path(argv[0]), int(argv[1]) if len(argv) > 1 else 0)
    print(f"created: {', '.join(created) or 'nothing'}")


if __name__ == "__main__":
    main(sys.argv[1:])
