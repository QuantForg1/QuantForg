"""QuantForg FastAPI application factory and entrypoint.

Creates the ASGI application with lifespan-managed infrastructure,
middleware, exception handlers, and foundation routers.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.presentation.middleware.access_log import RequestAccessLogMiddleware
from app.presentation.middleware.authentication import AuthenticationMiddleware
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.middleware.request_context import RequestContextMiddleware
from app.presentation.middleware.session import SessionMiddleware
from core.config.settings import Settings, get_settings
from core.database.session import DatabaseManager, set_database_manager
from core.di.container import Container, set_container
from core.logging import configure_logging, get_logger
from core.security.headers import SecurityHeaders

logger = get_logger(__name__)

# Routers are registered one-by-one (lazy import) so a single broken module
# can be skipped via QF_DISABLED_COMPONENTS without taking down the process.
_ROUTER_SPECS: tuple[tuple[str, str], ...] = (
    ("health", "app.presentation.routers.health"),
    ("version", "app.presentation.routers.version"),
    ("auth", "app.presentation.routers.auth"),
    ("profile", "app.presentation.routers.profile"),
    ("settings", "app.presentation.routers.settings"),
    ("notifications", "app.presentation.routers.notifications"),
    ("organizations", "app.presentation.routers.organizations"),
    ("brokers", "app.presentation.routers.brokers"),
    ("broker_accounts", "app.presentation.routers.broker_accounts"),
    ("broker_connections", "app.presentation.routers.broker_connections"),
    ("mt5", "app.presentation.routers.mt5"),
    ("execution", "app.presentation.routers.execution"),
    ("portfolio", "app.presentation.routers.portfolio"),
    ("risk", "app.presentation.routers.risk"),
    ("strategy", "app.presentation.routers.strategy"),
    ("backtest", "app.presentation.routers.backtest"),
    ("paper", "app.presentation.routers.paper"),
    ("walkforward", "app.presentation.routers.walkforward"),
    ("ops", "app.presentation.routers.ops"),
    ("intelligence", "app.presentation.routers.intelligence"),
    ("portfolio_intelligence", "app.presentation.routers.portfolio_intelligence"),
    ("execution_intelligence", "app.presentation.routers.execution_intelligence"),
    ("broker_connectivity", "app.presentation.routers.broker_connectivity"),
    ("gateway_manager", "app.presentation.routers.gateway_manager"),
    ("weltrade", "app.presentation.routers.weltrade"),
)


def _disabled_components() -> set[str]:
    """Component names to skip (comma-separated QF_DISABLED_COMPONENTS)."""
    raw = os.environ.get("QF_DISABLED_COMPONENTS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


_SECURITY_COMPONENTS = frozenset(
    {
        "cors",
        "trusted_host",
        "security_headers",
        "authentication",
        "session",
        "request_context",
        "proxy_headers",
        "rate_limit",
    }
)


def _is_disabled(name: str) -> bool:
    if name.lower() not in _disabled_components():
        return False
    env = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "")).lower()
    if env == "production" and name.lower() in _SECURITY_COMPONENTS:
        logger.warning(
            "security_component_disable_blocked",
            component=name,
            reason="production",
        )
        return False
    return True


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

    from urllib.parse import urlparse

    override = (settings.database_url_override or "").strip()
    supabase_pw = (
        settings.supabase_db_password.get_secret_value().strip()
        if settings.supabase_db_password is not None
        else ""
    )
    if override:
        dsn_source = "DATABASE_URL"
    elif supabase_pw and settings._supabase_project_ref:
        dsn_source = "SUPABASE_DB_PASSWORD"
    else:
        dsn_source = "POSTGRES_COMPOSED"
    resolved_host = urlparse(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    ).hostname

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
        database_url_configured=bool(override),
        database_dsn_source=dsn_source,
        database_resolved_host=resolved_host or "",
        redis_url_configured=bool((settings.redis_url_override or "").strip()),
        railway_public_domain=settings.railway_public_domain or "",
        mt5_gateway_base_url_configured=bool(
            (settings.mt5_gateway_base_url or "").strip()
        ),
        mt5_gateway_caller_token_configured=bool(
            (settings.mt5_gateway_caller_token or "").strip()
        ),
    )

    database = DatabaseManager(settings)
    container = Container(settings=settings, database=database)
    set_container(container)
    set_database_manager(database)
    # Keep FastAPI state in sync for any code that inspects app.state.container.
    _app.state.container = container

    try:
        await container.startup()
        gw_url = (settings.mt5_gateway_base_url or "").strip()
        gw_tok = bool((settings.mt5_gateway_caller_token or "").strip())
        logger.info(
            "application_started",
            name=settings.app_name,
            version=settings.app_version,
            env=settings.app_env.value,
            execution_enabled=bool(settings.execution_enabled),
            redis_connected=container.redis is not None,
            supabase_connected=container.supabase is not None,
            mt5_gateway_base_url_configured=bool(gw_url),
            mt5_gateway_caller_token_configured=gw_tok,
            mt5_gateway_backed=bool(
                gw_url
                and gw_tok
                and getattr(container, "mt5_adapter", None) is not None
            ),
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


def _register_middleware(application: FastAPI, settings: Settings) -> list[str]:
    """Register middleware one-by-one; skip components in QF_DISABLED_COMPONENTS."""
    registered: list[str] = []

    # Never pair allow_credentials with wildcard origins.
    cors_origins = [o for o in (settings.cors_origins or []) if o and o != "*"]
    if not _is_disabled("cors"):
        cors_kwargs: dict[str, Any] = {
            "allow_origins": cors_origins,
            "allow_credentials": bool(cors_origins),
            "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "X-Request-ID",
                "Accept",
                "Origin",
            ],
            "expose_headers": ["X-Request-ID"],
            "max_age": 600,
        }
        if settings.is_production:
            # Vercel production + preview hosts (never "*"). Exact origins from
            # CORS_ALLOWED_ORIGINS remain in allow_origins.
            cors_kwargs["allow_origin_regex"] = (
                r"https://([a-zA-Z0-9-]+\.)*vercel\.app"
            )
            # Bearer-token SPA calls still need credentials flag when an origin
            # matches via regex even if the static allowlist is empty.
            if not cors_origins:
                cors_kwargs["allow_credentials"] = True
        else:
            cors_kwargs["allow_origin_regex"] = r"https://.*\.up\.railway\.app"
        application.add_middleware(CORSMiddleware, **cors_kwargs)
        registered.append("cors")
        logger.info(
            "cors_middleware_enabled",
            allow_origins_count=len(cors_origins),
            allow_origin_regex=bool(cors_kwargs.get("allow_origin_regex")),
        )

    hosts = settings.allowed_hosts or ["*"]
    if "*" not in hosts and not _is_disabled("trusted_host"):
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=hosts,
        )
        registered.append("trusted_host")
        logger.info("trusted_host_middleware_enabled", allowed_hosts=hosts)
    else:
        logger.info(
            "trusted_host_middleware_skipped",
            reason="allowed_hosts=*" if "*" in hosts else "disabled",
        )

    if not _is_disabled("security_headers"):
        application.add_middleware(SecurityHeaders)
        registered.append("security_headers")
    if not _is_disabled("authentication"):
        application.add_middleware(AuthenticationMiddleware)
        registered.append("authentication")
    if not _is_disabled("session"):
        application.add_middleware(SessionMiddleware)
        registered.append("session")
    if not _is_disabled("request_context"):
        application.add_middleware(RequestContextMiddleware)
        registered.append("request_context")

    if not _is_disabled("proxy_headers"):
        application.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
        registered.append("proxy_headers")

    if not _is_disabled("rate_limit"):
        from app.presentation.middleware.rate_limit import AuthRateLimitMiddleware

        application.add_middleware(AuthRateLimitMiddleware)
        registered.append("rate_limit")

    if not _is_disabled("access_log"):
        application.add_middleware(RequestAccessLogMiddleware)
        registered.append("access_log")

    logger.info("middleware_stack_registered", components=registered)
    return registered


def _register_routers(application: FastAPI, settings: Settings) -> dict[str, Any]:
    """Import and mount routers one-by-one; skip failures and disabled names."""
    prefix = settings.api_prefix
    registered: list[str] = []
    failed: list[str] = []
    first_failure: str | None = None

    for name, module_path in _ROUTER_SPECS:
        if _is_disabled(name):
            logger.warning("router_skipped", router=name, reason="disabled")
            continue
        try:
            module = importlib.import_module(module_path)
            router = module.router
            application.include_router(router, prefix=prefix)
            registered.append(name)
            logger.info("router_registered", router=name, prefix=prefix)
        except Exception as exc:
            failed.append(name)
            if first_failure is None:
                first_failure = name
            logger.exception(
                "router_registration_failed",
                router=name,
                module=module_path,
                error=str(exc),
            )

    # Unprefixed health for Railway / platform probes (GET /health).
    if not _is_disabled("health") and "health" in registered:
        try:
            health_module = importlib.import_module("app.presentation.routers.health")
            application.include_router(health_module.router)
            logger.info("router_registered", router="health_unprefixed", prefix="")
        except Exception as exc:
            logger.exception(
                "router_registration_failed",
                router="health_unprefixed",
                error=str(exc),
            )

    summary = {
        "registered": registered,
        "failed": failed,
        "first_failure": first_failure,
    }
    logger.info("router_registration_complete", **summary)
    return summary


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

    _register_middleware(application, settings)
    register_exception_handlers(application)

    @application.get("/", tags=["Root"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"status": "ok"}

    _register_routers(application, settings)

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


app = create_app()


if __name__ == "__main__":
    run()
