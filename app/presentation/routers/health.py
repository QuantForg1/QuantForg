"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.application.dto.health import HealthStatus
from app.application.services.health_service import HealthService
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles
from app.presentation.dependencies.ops import OpsMetricsDep
from app.presentation.dependencies.services import get_health_service
from app.presentation.schemas.health import (
    DependencyStatusSchema,
    HealthResponse,
)
from app.presentation.schemas.ops import MetricsResponse
from core.config.settings import get_settings

router = APIRouter(tags=["Health"])


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
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def ready_alias() -> dict[str, str]:
    return {"status": "ok"}


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
    summary="Readiness probe (instant)",
    description="Immediate 200 — process accepts traffic. Use /health/status for deps.",
    status_code=status.HTTP_200_OK,
)
async def readiness() -> dict[str, str]:
    """Ready for edge probes — does not wait on infrastructure."""
    return {"status": "ok"}


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
