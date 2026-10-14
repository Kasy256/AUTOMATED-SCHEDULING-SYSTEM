import sentry_sdk

from cartlyf_api.settings import Settings


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(dsn=settings.sentry_dsn.get_secret_value(), send_default_pii=False)
