"""QuantForg FastAPI application factory and entrypoint.

Creates the ASGI application with lifespan-managed infrastructure,
middleware, exception handlers, and foundation routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI

from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.routers import (
    auth,
    backtest,
    broker_accounts,
    broker_connections,
    brokers,
    execution,
    health,
    mt5,
    notifications,
    ops,
    organizations,
    paper,
    portfolio,
    profile,
    risk,
    settings as settings_router,
    strategy,
    version,
    walkforward,
)
from core.config.settings import Settings, get_settings
from core.database.session import DatabaseManager, set_database_manager
from core.di.container import Container, set_container
from core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Startup
    -------
    1. Load settings and configure structured logging.
    2. Construct the DI container with database manager.
    3. Open PostgreSQL and Redis connections (optional deps fail soft).

    Shutdown
    --------
    1. Close Redis and PostgreSQL connections gracefully.
    """
    import sys

    settings = get_settings()
    configure_logging(settings)

    logger.info(
        "startup_diagnostics",
        python_version=sys.version.split()[0],
        app_env=settings.app_env.value,
        port=settings.port,
        host=settings.host,
        reload=settings.reload,
        debug=settings.debug,
        execution_enabled=bool(settings.execution_enabled),
        allowed_hosts=settings.allowed_hosts,
        database_url_configured=bool(
            (settings.database_url_override or "").strip() or settings.postgres_host
        ),
        redis_url_configured=bool((settings.redis_url_override or "").strip()),
        railway_public_domain=settings.railway_public_domain or "",
    )

    database = DatabaseManager(settings)
    container = Container(settings=settings, database=database)
    set_container(container)
    set_database_manager(database)

    try:
        await container.startup()
        logger.info(
            "application_started",
            name=settings.app_name,
            version=settings.app_version,
            env=settings.app_env.value,
            execution_enabled=bool(settings.execution_enabled),
            redis_connected=container.redis is not None,
            supabase_connected=container.supabase is not None,
        )
        logger.info("startup_complete")
    except Exception as exc:
        # Last-resort: keep process alive for liveness probes.
        logger.exception("application_startup_degraded", error=str(exc))

    yield

    try:
        await container.shutdown()
    except Exception as exc:
        logger.warning("application_shutdown_error", error=str(exc))
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

    docs_url = "/docs" if settings.docs_enabled else None
    redoc_url = "/redoc" if settings.docs_enabled else None
    openapi_url = "/openapi.json" if settings.docs_enabled else None

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "QuantForg v1.0.0 — Algorithmic Trading Platform. "
            "Live execution is DISABLED by default (EXECUTION_ENABLED=false). "
            "AI is not included in this release."
        ),
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Middleware temporarily disabled for Railway outage isolation.
    # Re-enable incrementally after GET / returns 200 at the edge.
    # (TrustedHost/Proxy/CORS/Auth/Session/AccessLog were candidates for
    # connection aborts behind railway-hikari.)
    logger.info("middleware_stack_disabled", reason="railway_outage_isolation")

    # -- Exception handlers ---------------------------------------------------
    register_exception_handlers(application)

    # -- Root + unprefixed health (Railway / platform probes) -----------------
    @application.get("/", tags=["Root"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(health.router)

    # -- Versioned API routers ------------------------------------------------
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
    application.include_router(mt5.router, prefix=prefix)
    application.include_router(execution.router, prefix=prefix)
    application.include_router(portfolio.router, prefix=prefix)
    application.include_router(risk.router, prefix=prefix)
    application.include_router(strategy.router, prefix=prefix)
    application.include_router(backtest.router, prefix=prefix)
    application.include_router(paper.router, prefix=prefix)
    application.include_router(walkforward.router, prefix=prefix)
    application.include_router(ops.router, prefix=prefix)

    return application


def run() -> None:
    """CLI entrypoint used by ``poetry run quantforg``."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload and settings.is_development,
        workers=1,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
        http="h11",
        loop="asyncio",
    )


def _select_app() -> Any:
    """Choose ASGI target.

    Default QF_MINIMAL=1 so Railway returns HTTP 200 even when the platform
    start command bypasses docker-entrypoint.sh and runs ``uvicorn app.main:app``.
    Set QF_MINIMAL=0 to restore the full application.
    """
    import os
    import sys

    minimal = os.environ.get("QF_MINIMAL", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if minimal:
        from app.raw_asgi import app as raw_app

        print(
            "qf_main_select_raw"
            f" type={type(raw_app)!r}"
            f" id={id(raw_app)}"
            f" python={sys.version.split()[0]}",
            flush=True,
        )
        return raw_app

    full = create_app()
    print(
        "qf_main_select_full"
        f" type={type(full)!r}"
        f" id={id(full)}"
        f" routes={len(full.routes)}"
        f" python={sys.version.split()[0]}",
        flush=True,
    )
    return full


app = _select_app()


if __name__ == "__main__":
    run()
