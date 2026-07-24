"""QuantForg FastAPI application factory and entrypoint.

Creates the ASGI application with lifespan-managed infrastructure,
middleware, exception handlers, and foundation routers.
"""

from __future__ import annotations

import asyncio
import contextlib
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

# Minimal routers required before Railway healthchecks. Everything else is
# registered after the server is listening (see lifespan deferred boot).
_CORE_ROUTER_NAMES: frozenset[str] = frozenset(
    {"health", "version", "auth", "beta_access"}
)

# Routers are registered one-by-one (lazy import) so a single broken module
# can be skipped via QF_DISABLED_COMPONENTS without taking down the process.
_ROUTER_SPECS: tuple[tuple[str, str], ...] = (
    ("health", "app.presentation.routers.health"),
    ("version", "app.presentation.routers.version"),
    ("beta_access", "app.presentation.routers.beta_access"),
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
    ("performance_intelligence", "app.presentation.routers.performance_intelligence"),
    ("replay_evidence_lab", "app.presentation.routers.replay_evidence_lab"),
    ("trading_operations_center", "app.presentation.routers.trading_operations_center"),
    ("audit_governance", "app.presentation.routers.audit_governance"),
    (
        "institutional_data_warehouse",
        "app.presentation.routers.institutional_data_warehouse",
    ),
    (
        "institutional_observability",
        "app.presentation.routers.institutional_observability",
    ),
    ("execution_intelligence", "app.presentation.routers.execution_intelligence"),
    ("quant_ai", "app.presentation.routers.quant_ai"),
    ("quant_studio", "app.presentation.routers.quant_studio"),
    ("decision_engine", "app.presentation.routers.decision_engine"),
    ("research_lab", "app.presentation.routers.research_lab"),
    ("institutional_research", "app.presentation.routers.institutional_research"),
    ("institutional_ops", "app.presentation.routers.institutional_ops"),
    ("institutional_reliability", "app.presentation.routers.institutional_reliability"),
    (
        "institutional_certification",
        "app.presentation.routers.institutional_certification",
    ),
    ("ecosystem", "app.presentation.routers.ecosystem"),
    ("broker_connectivity", "app.presentation.routers.broker_connectivity"),
    ("gateway_manager", "app.presentation.routers.gateway_manager"),
    ("weltrade", "app.presentation.routers.weltrade"),
    ("ai_trading_robot", "app.presentation.routers.ai_trading_robot"),
    (
        "institutional_ai_decision",
        "app.presentation.routers.institutional_ai_decision",
    ),
    ("market_intelligence", "app.presentation.routers.market_intelligence"),
    ("strategy_research_lab", "app.presentation.routers.strategy_research_lab"),
    ("decision_intelligence", "app.presentation.routers.decision_intelligence"),
    ("mission_control", "app.presentation.routers.mission_control"),
    ("intelligence_platform", "app.presentation.routers.intelligence_platform"),
    ("production_readiness", "app.presentation.routers.production_readiness"),
    ("production_replay", "app.presentation.routers.production_replay"),
    (
        "threshold_performance_analysis",
        "app.presentation.routers.threshold_performance_analysis",
    ),
    ("micro_account_analyzer", "app.presentation.routers.micro_account_analyzer"),
    ("alpha_engine", "app.presentation.routers.alpha_engine"),
    ("trading_kernel", "app.presentation.routers.trading_kernel"),
    ("multi_agent_ai", "app.presentation.routers.multi_agent_ai"),
    ("trading_brain_v3", "app.presentation.routers.trading_brain_v3"),
    (
        "research_validation_platform",
        "app.presentation.routers.research_validation_platform",
    ),
    ("scalping_ai_v2", "app.presentation.routers.scalping_ai_v2"),
    (
        "adaptive_scalping_intelligence",
        "app.presentation.routers.adaptive_scalping_intelligence",
    ),
    (
        "institutional_edge_engine",
        "app.presentation.routers.institutional_edge_engine",
    ),
    ("alpha_factory", "app.presentation.routers.alpha_factory"),
    (
        "institutional_validation_program",
        "app.presentation.routers.institutional_validation_program",
    ),
    (
        "real_market_intelligence_platform",
        "app.presentation.routers.real_market_intelligence_platform",
    ),
    (
        "live_learning_program",
        "app.presentation.routers.live_learning_program",
    ),
    (
        "production_readiness_certification",
        "app.presentation.routers.production_readiness_certification",
    ),
    (
        "integration_sprint_v1",
        "app.presentation.routers.integration_sprint_v1",
    ),
    (
        "institutional_research_lab",
        "app.presentation.routers.institutional_research_lab",
    ),
    (
        "ai_quant_scientist",
        "app.presentation.routers.ai_quant_scientist",
    ),
    (
        "ai_quant_copilot",
        "app.presentation.routers.ai_quant_copilot",
    ),
    (
        "quant_knowledge_graph",
        "app.presentation.routers.quant_knowledge_graph",
    ),
    (
        "execution_quality_suite",
        "app.presentation.routers.execution_quality_suite",
    ),
    (
        "reliability_engineering_suite",
        "app.presentation.routers.reliability_engineering_suite",
    ),
    (
        "continuous_validation_framework",
        "app.presentation.routers.continuous_validation_framework",
    ),
    (
        "institutional_simulation_engine",
        "app.presentation.routers.institutional_simulation_engine",
    ),
    (
        "institutional_release_deployment",
        "app.presentation.routers.institutional_release_deployment",
    ),
    (
        "institutional_risk_analytics",
        "app.presentation.routers.institutional_risk_analytics",
    ),
    (
        "institutional_strategy_lifecycle",
        "app.presentation.routers.institutional_strategy_lifecycle",
    ),
    (
        "institutional_experimentation_platform",
        "app.presentation.routers.institutional_experimentation_platform",
    ),
    (
        "institutional_control_plane",
        "app.presentation.routers.institutional_control_plane",
    ),
    (
        "quantforg_certification_suite",
        "app.presentation.routers.quantforg_certification_suite",
    ),
    (
        "quantforg_strategy_marketplace",
        "app.presentation.routers.quantforg_strategy_marketplace",
    ),
    (
        "quantforg_portfolio_manager",
        "app.presentation.routers.quantforg_portfolio_manager",
    ),
    (
        "quantforg_autonomous_operations",
        "app.presentation.routers.quantforg_autonomous_operations",
    ),
    (
        "quantforg_event_mesh",
        "app.presentation.routers.quantforg_event_mesh",
    ),
    (
        "quantforg_canonical_data_model",
        "app.presentation.routers.quantforg_canonical_data_model",
    ),
    (
        "quantforg_decision_intelligence",
        "app.presentation.routers.quantforg_decision_intelligence",
    ),
    (
        "quantforg_strategy_factory",
        "app.presentation.routers.quantforg_strategy_factory",
    ),
    (
        "quantforg_paper_trading_campaign",
        "app.presentation.routers.quantforg_paper_trading_campaign",
    ),
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

    Critical for Railway: yield as soon as the DI shell exists so
    ``/health/live`` can answer. Heavy DB / Redis / MT5 / ITE work runs in
    a background task and must never block the healthcheck window.
    """
    import sys
    import time

    t0 = time.perf_counter()
    print("Server starting...", flush=True)
    logger.info("server_starting")

    settings = get_settings()
    configure_logging(settings)
    port_env = os.environ.get("PORT") or str(settings.port)
    host_env = os.environ.get("HOST") or settings.host or "0.0.0.0"
    print("Environment loaded...", flush=True)
    logger.info(
        "environment_loaded",
        port=port_env,
        host=host_env,
        app_env=settings.app_env.value,
    )

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
        port=port_env,
        host=host_env,
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
        force_first_trade=bool(getattr(settings, "force_first_trade", False)),
    )
    try:
        from app.domain.institutional_trading.force_first_trade import (
            log_force_first_trade_startup,
        )

        log_force_first_trade_startup(settings)
    except Exception:
        logger.exception("force_first_trade_startup_log_failed")

    database = DatabaseManager(settings)
    container = Container(settings=settings, database=database)
    set_container(container)
    set_database_manager(database)
    _app.state.container = container
    shadow_task: asyncio.Task[Any] | None = None
    boot_task: asyncio.Task[Any] | None = None

    async def _deferred_boot() -> None:
        nonlocal shadow_task
        # Finish mounting non-core routers after listen (production path).
        pending = tuple(getattr(_app.state, "pending_router_specs", ()) or ())
        if pending:
            t_routes = time.perf_counter()
            _register_routers(
                _app,
                settings,
                specs=pending,
                mount_unprefixed_health=False,
            )
            print(
                f"AI: deferred routers {round((time.perf_counter() - t_routes) * 1000.0, 1)}ms",
                flush=True,
            )
            _app.state.pending_router_specs = ()

        t_db = time.perf_counter()
        try:
            await container.startup()
            db_ms = round((time.perf_counter() - t_db) * 1000.0, 1)
            logger.info("startup_timing", phase="database_and_infra_ms", ms=db_ms)
            print(f"Database: {db_ms}ms", flush=True)
            print("Gateway: scheduled (non-blocking recovery)", flush=True)

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
            runtime = getattr(container, "ite_runtime", None)
            if runtime is not None:
                shadow_task = asyncio.create_task(
                    runtime.run_forever(), name="ite-orchestrator"
                )
                logger.info(
                    "ite_orchestrator_task_started",
                    execution_enabled=bool(settings.execution_enabled),
                )
            total_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            logger.info("startup_complete", startup_total_ms=total_ms)
            print(f"Startup Total: {total_ms}ms", flush=True)
            if total_ms > 5000:
                logger.warning(
                    "startup_exceeded_5s",
                    startup_total_ms=total_ms,
                    hint="Check Database / AI(ITE) / Gateway recovery timing logs",
                )
        except Exception as exc:
            logger.exception("application_startup_degraded", error=str(exc))

    # Yield ASAP so Railway healthchecks succeed.
    # Tests default to sync boot (full wiring before yield). Production never blocks.
    print("Health endpoint ready...", flush=True)
    print(f"Listening on PORT {port_env}", flush=True)
    logger.info("health_endpoint_ready", port=port_env, host=host_env)
    ready_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    logger.info("startup_timing", phase="ready_to_serve_ms", ms=ready_ms)

    sync_env = os.environ.get("QF_SYNC_STARTUP", "").lower()
    if sync_env in {"0", "false", "no", "off"}:
        sync_boot = False
    elif sync_env in {"1", "true", "yes", "on"}:
        sync_boot = True
    else:
        sync_boot = bool(settings.is_testing)
    if sync_boot:
        await _deferred_boot()
    else:
        boot_task = asyncio.create_task(_deferred_boot(), name="deferred-boot")

    yield

    try:
        if boot_task is not None and not boot_task.done():
            boot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await boot_task
        runtime = getattr(container, "ite_runtime", None)
        if runtime is not None:
            runtime.stop()
        if shadow_task is not None:
            shadow_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await shadow_task
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
            # Vercel previews (*.vercel.app) + custom domain (*.quantforg.com).
            # Exact origins from CORS_ALLOWED_ORIGINS remain in allow_origins.
            from core.config.frontend_origins import PRODUCTION_CORS_ORIGIN_REGEX

            cors_kwargs["allow_origin_regex"] = PRODUCTION_CORS_ORIGIN_REGEX
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


def _register_routers(
    application: FastAPI,
    settings: Settings,
    *,
    specs: tuple[tuple[str, str], ...] | None = None,
    mount_unprefixed_health: bool = True,
) -> dict[str, Any]:
    """Import and mount routers one-by-one; skip failures and disabled names.

    Health is always registered first (and unprefixed) so Railway probes work
    even if a later institutional router fails to import.
    """
    import time

    t0 = time.perf_counter()
    prefix = settings.api_prefix
    registered: list[str] = []
    failed: list[str] = []
    first_failure: str | None = None
    selected = specs if specs is not None else _ROUTER_SPECS

    # Ensure health is first in the registration order.
    ordered = sorted(
        selected,
        key=lambda item: 0 if item[0] == "health" else 1,
    )

    for name, module_path in ordered:
        if _is_disabled(name):
            logger.warning("router_skipped", router=name, reason="disabled")
            continue
        t_r = time.perf_counter()
        try:
            module = importlib.import_module(module_path)
            router = module.router
            application.include_router(router, prefix=prefix)
            registered.append(name)
            ms = round((time.perf_counter() - t_r) * 1000.0, 1)
            logger.info("router_registered", router=name, prefix=prefix, ms=ms)
            if ms > 2000:
                logger.warning("router_registration_slow", router=name, ms=ms)
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

    # Unprefixed health for Railway / platform probes (GET /health, /health/live).
    if (
        mount_unprefixed_health
        and not _is_disabled("health")
        and "health" in registered
    ):
        try:
            health_module = importlib.import_module("app.presentation.routers.health")
            application.include_router(health_module.router)
            logger.info("router_registered", router="health_unprefixed", prefix="")
            print("Routes loaded...", flush=True)
            print("Health endpoint ready...", flush=True)
        except Exception as exc:
            logger.exception(
                "router_registration_failed",
                router="health_unprefixed",
                error=str(exc),
            )

    route_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    summary = {
        "registered": registered,
        "failed": failed,
        "first_failure": first_failure,
        "route_registration_ms": route_ms,
    }
    logger.info("router_registration_complete", **summary)
    print(f"Route Registration: {route_ms}ms", flush=True)
    if route_ms > 5000:
        logger.warning(
            "route_registration_exceeded_5s",
            route_registration_ms=route_ms,
            first_failure=first_failure,
        )
    return summary


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Parameters
    ----------
    settings:
        Optional settings override (useful in tests). When omitted the
        process-wide singleton from :func:`get_settings` is used.
    """
    import time

    t0 = time.perf_counter()
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

    # Production: register core probes only so create_app returns quickly and
    # Railway can healthcheck within seconds. Remaining routers load after listen.
    # Tests default to eager; override with QF_EAGER_ROUTERS=false for smoke.
    eager_env = os.environ.get("QF_EAGER_ROUTERS", "").lower()
    if eager_env in {"0", "false", "no", "off"}:
        eager = False
    elif eager_env in {"1", "true", "yes", "on"}:
        eager = True
    else:
        eager = bool(settings.is_testing)
    if eager:
        _register_routers(application, settings, specs=_ROUTER_SPECS)
        application.state.pending_router_specs = ()
    else:
        core_specs = tuple(
            s for s in _ROUTER_SPECS if s[0] in _CORE_ROUTER_NAMES
        )
        _register_routers(application, settings, specs=core_specs)
        application.state.pending_router_specs = tuple(
            s for s in _ROUTER_SPECS if s[0] not in _CORE_ROUTER_NAMES
        )

    total_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    logger.info("create_app_complete", ms=total_ms, eager_routers=eager)
    if total_ms > 5000:
        logger.warning("create_app_exceeded_5s", ms=total_ms)

    return application


def run() -> None:
    """CLI entrypoint used by ``poetry run quantforg``."""
    settings = get_settings()
    # Railway injects PORT; never prefer a baked 8000 over the platform port.
    port = int(os.environ.get("PORT") or settings.port)
    host = os.environ.get("HOST") or settings.host or "0.0.0.0"
    print(f"Listening on PORT {port} host={host}", flush=True)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
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
