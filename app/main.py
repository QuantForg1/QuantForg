"""QuantForg FastAPI application factory and entrypoint.

Creates the ASGI application with lifespan-managed infrastructure,
middleware, exception handlers, and foundation routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.presentation.middleware.authentication import AuthenticationMiddleware
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.middleware.request_context import RequestContextMiddleware
from app.presentation.middleware.session import SessionMiddleware
from app.presentation.routers import (
    auth,
    broker_accounts,
    broker_connections,
    brokers,
    health,
    notifications,
    organizations,
    profile,
    settings as settings_router,
    version,
)
from core.config.settings import Settings, get_settings
from core.database.session import DatabaseManager, set_database_manager
from core.di.container import Container, set_container
from core.logging import configure_logging, get_logger
from core.security.headers import SecurityHeaders

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Startup
    -------
    1. Load settings and configure structured logging.
    2. Construct the DI container with database manager.
    3. Open PostgreSQL and Redis connections.

    Shutdown
    --------
    1. Close Redis and PostgreSQL connections gracefully.
    """
    settings = get_settings()
    configure_logging(settings)

    database = DatabaseManager(settings)
    container = Container(settings=settings, database=database)
    set_container(container)
    set_database_manager(database)

    await container.startup()
    logger.info(
        "application_started",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env.value,
    )

    yield

    await container.shutdown()
    logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Parameters
    ----------
    settings:
        Optional settings override (useful in tests). When omitted the
        process-wide singleton from :func:`get_settings` is used.
    """
    if settings is None:
        settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "QuantForg — AI-Powered Algorithmic Trading Platform. "
            "Foundation API: health, version, and authentication."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # -- Middleware (order matters: last added = outermost) -------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    application.add_middleware(SecurityHeaders)
    application.add_middleware(AuthenticationMiddleware)
    application.add_middleware(SessionMiddleware)
    application.add_middleware(RequestContextMiddleware)

    # -- Exception handlers ---------------------------------------------------
    register_exception_handlers(application)

    # -- Routers --------------------------------------------------------------
    prefix = settings.api_prefix
    application.include_router(health.router, prefix=prefix)
    application.include_router(version.router, prefix=prefix)
    application.include_router(auth.router, prefix=prefix)
    application.include_router(profile.router, prefix=prefix)
    application.include_router(settings_router.router, prefix=prefix)
    application.include_router(notifications.router, prefix=prefix)
    application.include_router(organizations.router, prefix=prefix)
    application.include_router(brokers.router, prefix=prefix)
    application.include_router(broker_accounts.router, prefix=prefix)
    application.include_router(broker_connections.router, prefix=prefix)

    return application


app = create_app()


def run() -> None:
    """CLI entrypoint used by ``poetry run quantforg``."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload and settings.is_development,
        workers=settings.workers if not settings.reload else 1,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
