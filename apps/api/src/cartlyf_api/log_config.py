import logging
import re

import structlog
from structlog.tracebacks import ExceptionDictTransformer

# A calendar feed's token is its only credential, so request paths are logged without it.
_FEED_TOKEN = re.compile(r"(/calendar/)[^/?#\s]+(\.ics)")


def redact_feed_tokens(text: str) -> str:
    return _FEED_TOKEN.sub(r"\1[redacted]\2", text)


class _RedactFeedTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_feed_tokens(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Locals can hold passwords and tokens; never log them.
            structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False)),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _RedactFeedTokens) for f in access.filters):
        access.addFilter(_RedactFeedTokens())
