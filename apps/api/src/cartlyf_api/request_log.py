import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cartlyf_api.log_config import redact_feed_tokens

log = structlog.get_logger()


class RequestLog:
    """One JSON line per request; never the query string, headers or body (they carry secrets)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            client = scope.get("client")
            log.info(
                "http_request",
                method=scope["method"],
                path=redact_feed_tokens(scope["path"]),
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000),
                client_ip=client[0] if client else None,
            )
