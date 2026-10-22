from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from cartlyf_api.activities.router import router as activities_router
from cartlyf_api.auth.router import router as auth_router
from cartlyf_api.constraints.router import router as constraints_router
from cartlyf_api.db import create_db_engine
from cartlyf_api.email.provider import ConsoleEmailProvider
from cartlyf_api.errors import install_error_handlers
from cartlyf_api.feeds.router import router as feeds_router
from cartlyf_api.health.router import router as health_router
from cartlyf_api.imports.router import router as imports_router
from cartlyf_api.industry_templates.router import router as industry_templates_router
from cartlyf_api.jobs.broker import make_broker
from cartlyf_api.log_config import configure_logging
from cartlyf_api.orgs.router import router as orgs_router
from cartlyf_api.platform.router import router as platform_router
from cartlyf_api.problems.router import router as problems_router
from cartlyf_api.redis_client import connect_redis
from cartlyf_api.request_log import RequestLog
from cartlyf_api.resources.router import router as resources_router
from cartlyf_api.schedules.router import router as schedules_router
from cartlyf_api.sentry import init_sentry
from cartlyf_api.settings import Settings, load_settings
from cartlyf_api.solves.notifier import SolveNotifier, asyncpg_connector
from cartlyf_api.solves.router import router as solves_router
from cartlyf_api.storage import S3ObjectStore
from cartlyf_api.versions.router import router as versions_router


def _operation_id(route: APIRoute) -> str:
    return route.name


def web_origin(settings: Settings) -> str:
    url = settings.web_base_url
    port = f":{url.port}" if url.port not in (None, 80, 443) else ""
    return f"{url.scheme}://{url.host}{port}"


class WebOriginCors:
    """CORS for the web app's origin only; built on first request, once settings are resolved."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.cors: CORSMiddleware | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.cors is None:
            settings: Settings = scope["app"].state.settings
            self.cors = CORSMiddleware(
                self.app,
                allow_origins=[web_origin(settings)],
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                allow_headers=["Authorization", "Content-Type"],
                expose_headers=["Retry-After", "Content-Disposition"],
            )
        await self.cors(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    # Settings resolve at startup, so the OpenAPI schema can be exported without any env.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        resolved = settings or load_settings()
        configure_logging(resolved.log_level)
        init_sentry(resolved)
        app.state.settings = resolved
        app.state.db_engine = create_db_engine(resolved)
        app.state.redis = connect_redis(str(resolved.redis_url), resolved.db_timeout_seconds)
        app.state.email_provider = ConsoleEmailProvider()
        app.state.object_store = S3ObjectStore(resolved)
        app.state.broker = make_broker(str(resolved.redis_url), resolved.db_timeout_seconds)
        app.state.solve_notifier = SolveNotifier(asyncpg_connector(resolved))
        yield
        await app.state.solve_notifier.close()
        app.state.broker.close()
        await app.state.redis.aclose()
        await app.state.db_engine.dispose()

    app = FastAPI(
        title="Cartlyf API",
        version="0.0.0",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
    )
    install_error_handlers(app)
    app.add_middleware(WebOriginCors)
    app.add_middleware(RequestLog)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(orgs_router, prefix="/api/v1")
    app.include_router(platform_router, prefix="/api/v1")
    app.include_router(resources_router, prefix="/api/v1")
    app.include_router(schedules_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(constraints_router, prefix="/api/v1")
    app.include_router(problems_router, prefix="/api/v1")
    app.include_router(solves_router, prefix="/api/v1")
    app.include_router(versions_router, prefix="/api/v1")
    app.include_router(feeds_router, prefix="/api/v1")
    app.include_router(imports_router, prefix="/api/v1")
    app.include_router(industry_templates_router, prefix="/api/v1")
    return app
