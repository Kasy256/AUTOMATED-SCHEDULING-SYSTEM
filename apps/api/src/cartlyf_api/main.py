from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from cartlyf_api.auth.router import router as auth_router
from cartlyf_api.db import create_db_engine
from cartlyf_api.email.provider import ConsoleEmailProvider
from cartlyf_api.errors import install_error_handlers
from cartlyf_api.health.router import router as health_router
from cartlyf_api.log_config import configure_logging
from cartlyf_api.orgs.router import router as orgs_router
from cartlyf_api.platform.router import router as platform_router
from cartlyf_api.redis_client import connect_redis
from cartlyf_api.resources.router import router as resources_router
from cartlyf_api.settings import Settings, load_settings
from cartlyf_api.storage import S3ObjectStore


def _operation_id(route: APIRoute) -> str:
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    # Settings resolve at startup, so the OpenAPI schema can be exported without any env.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        resolved = settings or load_settings()
        configure_logging(resolved.log_level)
        app.state.settings = resolved
        app.state.db_engine = create_db_engine(resolved)
        app.state.redis = connect_redis(str(resolved.redis_url), resolved.db_timeout_seconds)
        app.state.email_provider = ConsoleEmailProvider()
        app.state.object_store = S3ObjectStore(resolved)
        yield
        await app.state.redis.aclose()
        await app.state.db_engine.dispose()

    app = FastAPI(
        title="Cartlyf API",
        version="0.0.0",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
    )
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(orgs_router, prefix="/api/v1")
    app.include_router(platform_router, prefix="/api/v1")
    app.include_router(resources_router, prefix="/api/v1")
    return app
