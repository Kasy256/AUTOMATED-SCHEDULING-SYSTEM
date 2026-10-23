"""OPS-04: 50 planners on the board + 5 concurrent solves.

    CARTLYF_ACCOUNTS=accounts.json uv run --group load locust -f tools/loadtest/locustfile.py \
        --host https://api-staging.<domain> --headless -u 55 -r 5 -t 10m --csv out/ops04

accounts.json comes from tools/seed_demo.py with at least 5 load orgs. Planners share one token
per org (the auth endpoints allow 10 logins per minute per IP); each solver owns one load org,
since an org may only run two solves at once.
"""

import itertools
import json
import os
import random
from pathlib import Path
from typing import Any

from gevent.lock import Semaphore
from locust import HttpUser, between, events, task

from tools.loadtest.moves import move_for

ACCOUNTS: dict[str, dict[str, str]] = json.loads(Path(os.environ["CARTLYF_ACCOUNTS"]).read_text())
LOAD_ORGS = sorted(label for label in ACCOUNTS if label.startswith("load-"))
_tokens: dict[str, str] = {}
_login_lock = Semaphore()
_solver_orgs = itertools.cycle(LOAD_ORGS)
SOLVE_TIME_LIMIT_S = 60


def _token(user: HttpUser, label: str, renew: bool = False) -> str:
    with _login_lock:
        if renew or label not in _tokens:
            account = ACCOUNTS[label]
            response = user.client.post(
                "/api/v1/auth/login",
                json={"email": account["email"], "password": account["password"]},
                name="login",
            )
            response.raise_for_status()
            _tokens[label] = response.json()["access_token"]
        return _tokens[label]


class OrgUser(HttpUser):
    abstract = True
    label = ""

    def call(self, method: str, path: str, name: str, **kwargs: Any) -> Any:
        for renew in (False, True):
            headers = {"Authorization": f"Bearer {_token(self, self.label, renew)}"}
            with self.client.request(
                method, path, headers=headers, name=name, catch_response=True, **kwargs
            ) as response:
                if response.status_code == 401 and not renew:
                    response.success()  # expired token: log in again and retry once
                    continue
                if response.status_code >= 400:
                    response.failure(f"{response.status_code} {response.text[:200]}")
                    return None
                return response
        return None


class PlannerUser(OrgUser):
    weight = 10
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.label = random.choice(LOAD_ORGS)
        self.schedule_id = ACCOUNTS[self.label]["schedule_id"]

    @task
    def work_the_board(self) -> None:
        listed = self.call("GET", f"/api/v1/schedules/{self.schedule_id}/versions", "list versions")
        if listed is None or not listed.json():
            return
        newest = max(listed.json(), key=lambda v: v["number"])
        detail = self.call("GET", f"/api/v1/solution-versions/{newest['id']}", "get version")
        if detail is None:
            return
        move = move_for(detail.json(), random.Random())
        if move is not None:
            self.call(
                "POST",
                f"/api/v1/solution-versions/{newest['id']}/validate-move",
                "validate-move",
                json=move,
            )


class SolverUser(OrgUser):
    fixed_count = 5
    wait_time = between(5, 10)

    def on_start(self) -> None:
        self.label = next(_solver_orgs)
        self.schedule_id = ACCOUNTS[self.label]["schedule_id"]

    @task
    def solve(self) -> None:
        started = self.call(
            "POST",
            f"/api/v1/schedules/{self.schedule_id}/solves",
            "start solve",
            json={"time_limit_s": SOLVE_TIME_LIMIT_S},
        )
        if started is None:
            return
        run_id = started.json()["id"]
        stream = self.call(
            "GET",
            f"/api/v1/solves/{run_id}/events",
            "solve events (until done)",
            stream=True,
            timeout=SOLVE_TIME_LIMIT_S * 5,
        )
        if stream is None:
            return
        done = _done_status(stream.iter_lines(decode_unicode=True))
        if done not in ("succeeded",):
            events.request.fire(
                request_type="SOLVE",
                name="solve outcome",
                response_time=0,
                response_length=0,
                exception=RuntimeError(f"solve ended {done}"),
            )


def _done_status(lines: Any) -> str | None:
    event = None
    for line in lines:
        if line.startswith("event: "):
            event = line[len("event: ") :]
        elif line.startswith("data: ") and event == "done":
            return json.loads(line[len("data: ") :])["status"]
    return None
