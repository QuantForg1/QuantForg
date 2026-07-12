"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.application.dto.health import HealthStatus
from app.application.services.health_service import HealthService
from app.presentation.dependencies.services import get_health_service
from app.presentation.schemas.health import (
    DependencyStatusSchema,
    HealthResponse,
)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness probe",
    description=(
        "Returns the aggregated health of the application and its "
        "infrastructure dependencies (PostgreSQL, Redis). "
        "Responds with HTTP 200 when healthy, 503 when unhealthy."
    ),
)
async def health_check(
    response: Response,
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """Execute health probes and return a structured report."""
    report = await service.check()

    if report.status != HealthStatus.HEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=report.status.value,
        version=report.version,
        environment=report.environment,
        dependencies=[
            DependencyStatusSchema(
                name=dep.name,
                status=dep.status.value,
                latency_ms=dep.latency_ms,
            )
            for dep in report.dependencies
        ],
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Returns 200 if the process is alive. Does not check dependencies.",
    status_code=status.HTTP_200_OK,
)
async def liveness() -> dict[str, str]:
    """Kubernetes-style liveness probe — process is running."""
    return {"status": "alive"}
