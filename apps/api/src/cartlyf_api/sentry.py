from uuid import UUID

import sentry_sdk
import structlog

from cartlyf_api.settings import Settings

log = structlog.get_logger()


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(dsn=settings.sentry_dsn.get_secret_value(), send_default_pii=False)


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
