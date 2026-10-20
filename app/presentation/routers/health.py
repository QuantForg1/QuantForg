"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from app.application.dto.health import HealthStatus
from app.application.services.health_service import HealthService
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles
from app.presentation.dependencies.ops import OpsMetricsDep
from app.presentation.dependencies.services import get_health_service
from app.presentation.router_boot import evaluate_readiness
from app.presentation.schemas.health import (
    DependencyStatusSchema,
    HealthResponse,
)
from app.presentation.schemas.ops import MetricsResponse
from core.config.settings import get_settings

router = APIRouter(tags=["Health"])


def _readiness_payload(request: Request) -> dict[str, Any]:
    """Derive readiness from router boot state (no secrets / stack traces)."""
    boot = getattr(request.app.state, "router_boot", None)
    if not isinstance(boot, dict):
        boot = None
    return evaluate_readiness(boot)


def _to_response(report: object) -> HealthResponse:
    return HealthResponse(
        status=report.status.value,  # type: ignore[attr-defined]
        version=report.version,  # type: ignore[attr-defined]
        environment=report.environment,  # type: ignore[attr-defined]
        dependencies=[
            DependencyStatusSchema(
                name=dep.name,
                status=dep.status.value,
                latency_ms=dep.latency_ms,
            )
            for dep in report.dependencies  # type: ignore[attr-defined]
        ],
    )


def _maybe_503(response: Response, report_status: HealthStatus) -> None:
    """Only emit 503 when HEALTH_HTTP_STRICT=true (off by default for Railway)."""
    if get_settings().health_http_strict and report_status != HealthStatus.HEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE


@router.get(
    "/health",
    summary="Platform health (instant)",
    description="Immediate 200 for Railway / load balancers. No dependency I/O.",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, str]:
    """Instant liveness — never blocks on DB, Redis, or MT5."""
    return {"status": "ok"}


@router.get(
    "/healthz",
    summary="Alias liveness probe",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Alias ready probe",
    include_in_schema=False,
)
async def ready_alias(request: Request, response: Response) -> dict[str, Any]:
    """Same semantics as ``/health/ready`` (router init, not DB)."""
    return await readiness(request, response)


@router.get(
    "/health/status",
    response_model=HealthResponse,
    summary="Detailed dependency health",
    description=(
        "Aggregated health of PostgreSQL / Redis. "
        "HTTP 200 by default; set HEALTH_HTTP_STRICT=true for 503 on failure."
    ),
)
async def health_status(
    response: Response,
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """Execute dependency probes and return a structured report."""
    report = await service.check()
    _maybe_503(response, report.status)
    return _to_response(report)


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description=(
        "Reports whether required API routers finished registration. "
        "Returns HTTP 503 while deferred routers are still pending or when a "
        "critical router failed to import. Does not probe Postgres/Redis/MT5 "
        "(use /health/status and /health/trading-components). "
        "Railway platform healthcheck should use /health/live."
    ),
)
async def readiness(request: Request, response: Response) -> dict[str, Any]:
    """Router-init readiness — not a full dependency health check."""
    payload = _readiness_payload(request)
    if not payload.get("http_ready", True):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    body: dict[str, Any] = {
        "status": payload["status"],
        "detail": payload.get("detail"),
        "routers": payload.get("routers"),
    }
    return body


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Returns 200 if the process is alive. Does not check dependencies.",
    status_code=status.HTTP_200_OK,
)
async def liveness() -> dict[str, str]:
    """Kubernetes / Railway liveness — process is running."""
    return {"status": "ok"}



@router.get(
    "/health/openai",
    summary="OpenAI advisor provider status",
    description=(
        "Observe-only OpenAI configuration status (no network call, no key "
        "exposure). Advisory only — never authorizes trades. Gemini is not used."
    ),
    status_code=status.HTTP_200_OK,
)
async def openai_provider_health() -> dict[str, object]:
    from app.application.services.openai_advisor_service import (
        build_openai_advisor_from_settings,
    )

    advisor = build_openai_advisor_from_settings(get_settings())
    payload = advisor.provider_status().to_dict()
    payload["status"] = "ok"
    return payload


@router.get(
    "/health/trading-components",
    summary="Trading component health (Gateway/OMS/MT5/AI)",
    description=(
        "Observe-only component statuses derived from live gateway probes and "
        "ITE runtime presence. Never fabricates HEALTHY. Does not enable "
        "execution or change strategy. Gateway-only probe (no Railway "
        "self-probe); short process cache for concurrent Mission Control cards."
    ),
    status_code=status.HTTP_200_OK,
)
async def trading_components_health() -> dict[str, object]:
    """Return Gateway / OMS / MT5 / AI health for production readiness."""
    from starlette.concurrency import run_in_threadpool

    from app.application.services.production_component_health import (
        collect_trading_component_health,
    )

    # Sync httpx probes must not block the async event loop / other requests.
    payload = await run_in_threadpool(
        collect_trading_component_health, get_settings()
    )
    payload["status"] = "ok"
    return payload


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Operational metrics",
    description=(
        "Returns request latency, error rate, throughput, cache hit ratio, "
        "and job duration metrics. Requires owner/admin. "
        "Does not enable execution or AI."
    ),
)
async def metrics(
    _admin: Annotated[
        object,
        Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    ],
    uc: OpsMetricsDep,
) -> MetricsResponse:
    """Authenticated metrics snapshot for operators."""
    dto = await uc.execute(persist=False)
    return MetricsResponse(**dto.payload)
