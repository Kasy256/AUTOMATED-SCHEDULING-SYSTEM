from typing import Any, cast
from uuid import UUID

import sentry_sdk
import structlog
from sentry_sdk.types import Event, Hint

from cartlyf_api.log_config import redact_feed_tokens
from cartlyf_api.settings import Settings

log = structlog.get_logger()


def sentry_options(settings: Settings) -> dict[str, Any]:
    assert settings.sentry_dsn is not None
    # No frame locals: an ASGI scope local carries the calendar feed token in its path.
    # scrub_event re-applies the request rules in case an integration ignores these.
    return {
        "dsn": settings.sentry_dsn.get_secret_value(),
        "data_collection": {
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_headers": {"request": {"mode": "denylist"}},
            "http_bodies": [],
            "url_query_params": {"mode": "off"},
            "database_query_data": False,
            "stack_frame_variables": False,
        },
        "before_send": scrub_event,
        "environment": settings.environment,
        "release": settings.release,
    }


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(**sentry_options(settings))


_SECRET_HEADERS = {"authorization", "cookie", "x-forwarded-for"}


def scrub_event(event: Event, _: Hint) -> Event:
    """Bodies, cookies, query strings and auth headers can carry passwords and tokens."""
    event.pop("user", None)
    request = event.get("request")
    if request is None:
        return event
    for key in ("data", "cookies", "query_string"):
        request.pop(key, None)
    url = request.get("url")
    if isinstance(url, str):
        request["url"] = redact_feed_tokens(url)
    headers = request.get("headers")
    if isinstance(headers, dict):
        kept = cast(dict[str, object], headers)
        request["headers"] = {k: v for k, v in kept.items() if k.lower() not in _SECRET_HEADERS}
    return event


def _tag(scope: sentry_sdk.Scope, run_id: UUID, organisation_id: UUID) -> None:
    scope.set_tag("run_id", str(run_id))
    scope.set_tag("organisation_id", str(organisation_id))


def report_failed_verification(run_id: UUID, organisation_id: UUID, hard_violations: int) -> None:
    """Solver and checker disagreeing is a P0 bug: alert, never store the result."""
    log.error(
        "solve_failed_verification",
        run_id=str(run_id),
        organisation_id=str(organisation_id),
        hard_violations=hard_violations,
    )
    with sentry_sdk.new_scope() as scope:
        _tag(scope, run_id, organisation_id)
        # One issue for every occurrence, so the alert rule can match it.
        scope.fingerprint = ["solve_failed_verification"]
        sentry_sdk.capture_message("solve_failed_verification", level="error")


def report_worker_error(run_id: UUID, organisation_id: UUID, exc: BaseException) -> None:
    log.error(
        "solve_worker_error",
        run_id=str(run_id),
        organisation_id=str(organisation_id),
        exc_info=exc,
    )
    with sentry_sdk.new_scope() as scope:
        _tag(scope, run_id, organisation_id)
        sentry_sdk.capture_exception(exc)
