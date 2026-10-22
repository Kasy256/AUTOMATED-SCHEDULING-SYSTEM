"""Post-deploy smoke test: `python tools/smoke.py <api-url> <web-url>`; exits 1 on any failure."""

import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

TIMEOUT_S = 30


def _fetch(
    url: str, method: str = "GET", headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _check_health(api_url: str) -> list[str]:
    status, _, body = _fetch(f"{api_url}/api/v1/health")
    if status != 200:
        return [f"health returned {status}"]
    role = json.loads(body).get("database", {})
    if role.get("rolsuper") is not False or role.get("rolbypassrls") is not False:
        return [f"unsafe database role: {role}"]
    return []


def _check_cors(api_url: str, web_url: str) -> list[str]:
    origin = _origin(web_url)
    _, headers, _ = _fetch(
        f"{api_url}/api/v1/auth/login",
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    lower = {k.lower(): v for k, v in headers.items()}
    allowed = lower.get("access-control-allow-origin")
    if allowed != origin or lower.get("access-control-allow-credentials") != "true":
        return [f"CORS preflight from {origin} allowed {allowed!r}"]
    return []


def _check_web(web_url: str) -> list[str]:
    status, _, body = _fetch(f"{web_url}/")
    if status != 200 or b'<div id="root">' not in body:
        return [f"web app returned {status} without the root element"]
    return []


def smoke(api_url: str, web_url: str) -> list[str]:
    api_url, web_url = api_url.rstrip("/"), web_url.rstrip("/")
    return _check_health(api_url) + _check_cors(api_url, web_url) + _check_web(web_url)


def main(argv: list[str]) -> int:
    failures = smoke(argv[0], argv[1])
    for failure in failures:
        print(f"FAIL {failure}")
    print("smoke: ok" if not failures else f"smoke: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
