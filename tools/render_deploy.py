"""Release steps on Render, driven from CI through the Render API.

    python tools/render_deploy.py deploy <service-id> <commit>
    python tools/render_deploy.py job <service-id> <command...>

Needs RENDER_API_KEY. Exits 1 if the deploy or job does not succeed.
"""

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass

DEPLOY_FAILED = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}


class DeployFailed(Exception):
    pass


@dataclass(frozen=True)
class RenderApi:
    base_url: str
    api_key: str
    poll_s: float = 10
    timeout_s: float = 1800

    def call(self, method: str, path: str, body: object | None = None) -> dict[str, object]:
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())


def _wait(api: RenderApi, path: str, done: set[str], failed: set[str], what: str) -> None:
    deadline = time.monotonic() + api.timeout_s
    while time.monotonic() < deadline:
        status = api.call("GET", path).get("status")
        print(f"{what}: {status}", flush=True)
        if status in done:
            return
        if status in failed:
            raise DeployFailed(f"{what} ended {status}")
        time.sleep(api.poll_s)
    raise DeployFailed(f"{what} timed out after {api.timeout_s:.0f} s")


def deploy_and_wait(api: RenderApi, service_id: str, commit: str) -> None:
    deploy = api.call("POST", f"/services/{service_id}/deploys", {"commitId": commit})
    path = f"/services/{service_id}/deploys/{deploy['id']}"
    _wait(api, path, {"live"}, DEPLOY_FAILED, f"deploy {service_id}")


def run_job_and_wait(api: RenderApi, service_id: str, command: str) -> None:
    job = api.call("POST", f"/services/{service_id}/jobs", {"startCommand": command})
    path = f"/services/{service_id}/jobs/{job['id']}"
    _wait(api, path, {"succeeded"}, {"failed", "canceled"}, f"job {service_id}")


def main(argv: list[str]) -> int:
    api = RenderApi("https://api.render.com/v1", os.environ["RENDER_API_KEY"])
    try:
        if argv[0] == "deploy":
            deploy_and_wait(api, argv[1], argv[2])
        elif argv[0] == "job":
            run_job_and_wait(api, argv[1], " ".join(argv[2:]))
        else:
            raise SystemExit(f"unknown step {argv[0]!r}")
    except DeployFailed as exc:
        print(f"FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
