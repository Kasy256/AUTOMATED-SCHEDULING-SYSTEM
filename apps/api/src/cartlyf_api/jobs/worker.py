"""Worker entrypoint: `dramatiq cartlyf_api.jobs.worker`."""

from cartlyf_api.jobs.broker import setup_broker
from cartlyf_api.log_config import configure_logging
from cartlyf_api.sentry import init_sentry
from cartlyf_api.settings import load_settings

_settings = load_settings()
configure_logging(_settings.log_level)
init_sentry(_settings)
setup_broker(str(_settings.redis_url), _settings.db_timeout_seconds)

# Actors bind to the global broker at import time, so they must be imported after setup.
from cartlyf_api.jobs import actors as actors  # noqa: E402
