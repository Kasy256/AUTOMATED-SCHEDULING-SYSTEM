import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tools.render_deploy import DeployFailed, RenderApi, deploy_and_wait, run_job_and_wait


class FakeRender:
    def __init__(self) -> None:
        self.url = ""
        self.deploy_statuses = ["build_in_progress", "update_in_progress", "live"]
        self.job_statuses: list[str | None] = [None, None, "succeeded"]
        self.requests: list[tuple[str, str, object, str]] = []


@pytest.fixture
def render() -> Iterator[FakeRender]:
    fake = FakeRender()

    class H(BaseHTTPRequestHandler):
        def _reply(self, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(201 if self.command == "POST" else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _record(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            fake.requests.append((self.command, self.path, body, self.headers["Authorization"]))

        def do_POST(self) -> None:
            self._record()
            if self.path.endswith("/deploys"):
                self._reply({"id": "dep-1", "status": "created"})
            else:
                self._reply({"id": "job-1", "status": None})

        def do_GET(self) -> None:
            self._record()
            if "/deploys/" in self.path:
                self._reply({"id": "dep-1", "status": fake.deploy_statuses.pop(0)})
            else:
                status = fake.job_statuses.pop(0)
                self._reply({"id": "job-1", "status": status, "finishedAt": status and "now"})

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    fake.url = f"http://127.0.0.1:{server.server_port}/v1"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield fake
    finally:
        server.shutdown()


def _api(render: FakeRender) -> RenderApi:
    return RenderApi(render.url, "rnd_key", poll_s=0, timeout_s=5)


def test_deploy_posts_the_commit_and_waits_for_live(render: FakeRender) -> None:
    deploy_and_wait(_api(render), "srv-api", "abc123")
    method, path, body, auth = render.requests[0]
    assert (method, path, body, auth) == (
        "POST",
        "/v1/services/srv-api/deploys",
        {"commitId": "abc123"},
        "Bearer rnd_key",
    )
    assert render.requests[-1][1] == "/v1/services/srv-api/deploys/dep-1"
    assert render.deploy_statuses == []


@pytest.mark.parametrize("status", ["build_failed", "update_failed", "canceled", "deactivated"])
def test_deploy_failure_raises(render: FakeRender, status: str) -> None:
    render.deploy_statuses = ["build_in_progress", status]
    with pytest.raises(DeployFailed, match=status):
        deploy_and_wait(_api(render), "srv-api", "abc123")


def test_job_runs_the_command_and_waits_for_success(render: FakeRender) -> None:
    run_job_and_wait(_api(render), "srv-migrate", "alembic upgrade head")
    assert render.requests[0][:3] == (
        "POST",
        "/v1/services/srv-migrate/jobs",
        {"startCommand": "alembic upgrade head"},
    )
    assert render.requests[-1][1] == "/v1/services/srv-migrate/jobs/job-1"


def test_failed_job_raises(render: FakeRender) -> None:
    render.job_statuses = [None, "failed"]
    with pytest.raises(DeployFailed, match="failed"):
        run_job_and_wait(_api(render), "srv-migrate", "alembic upgrade head")


def test_wait_gives_up_after_the_timeout(render: FakeRender) -> None:
    render.deploy_statuses = ["build_in_progress"] * 1000
    api = RenderApi(render.url, "rnd_key", poll_s=0.01, timeout_s=0.2)
    with pytest.raises(DeployFailed, match="timed out"):
        deploy_and_wait(api, "srv-api", "abc123")
