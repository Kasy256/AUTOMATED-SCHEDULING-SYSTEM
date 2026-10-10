import dramatiq
import structlog

log = structlog.get_logger()


@dramatiq.actor
def ping() -> None:
    log.info("ping")
