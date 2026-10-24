"""Re-delivery sweep: `python -m cartlyf_api.email.redeliver`, run by a Render cron."""

import asyncio

import structlog

from cartlyf_api.db import create_db_engine
from cartlyf_api.email.outbox import redeliver_pending
from cartlyf_api.email.provider import make_email_provider
from cartlyf_api.log_config import configure_logging
from cartlyf_api.sentry import init_sentry
from cartlyf_api.settings import Settings, load_settings

log = structlog.get_logger()


async def run_sweep(settings: Settings) -> int:
    engine = create_db_engine(settings)
    try:
        provider = make_email_provider(settings)
        return await redeliver_pending(engine, provider, settings.email_max_attempts)
    finally:
        await engine.dispose()


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    init_sentry(settings)
    log.info("email_redelivery_done", sent=asyncio.run(run_sweep(settings)))


if __name__ == "__main__":
    main()
