"""Unit tests for API endpoints that do not require live infrastructure.

Health endpoints that probe Postgres/Redis are covered in integration tests.
Version and liveness are pure and tested here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.health import DependencyStatus, HealthReport, HealthStatus
from app.application.dto.ops import OpsMetricsDTO
from app.application.dto.version import VersionInfo
from app.application.services.health_service import HealthService
from app.application.services.version_service import VersionService
from app.application.use_cases.ops import GetOpsMetricsUseCase
from app.presentation.dependencies.ops import get_ops_metrics_uc
from app.presentation.dependencies.services import (
    get_health_service,
    get_version_service,
)
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.routers.health import router as health_router
from app.presentation.routers.version import router as version_router


def _build_test_app() -> FastAPI:
    """Minimal FastAPI app with only foundation routers and mocked services."""
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(health_router)  # Railway unprefixed probes
    application.include_router(version_router, prefix="/api/v1")

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok"}

    mock_version = MagicMock(spec=VersionService)
    mock_version.get_version.return_value = VersionInfo(
        name="QuantForg",
        version="0.1.0",
        environment="testing",
        api_prefix="/api/v1",
    )

    mock_health = MagicMock(spec=HealthService)
    mock_health.check = AsyncMock(
        return_value=HealthReport(
            status=HealthStatus.HEALTHY,
            version="0.1.0",
            environment="testing",
            dependencies=[
                DependencyStatus(
                    name="postgres",
                    status=HealthStatus.HEALTHY,
                    latency_ms=1.2,
                ),
                DependencyStatus(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=0.5,
                ),
            ],
        )
    )

    mock_metrics_uc = MagicMock(spec=GetOpsMetricsUseCase)
    mock_metrics_uc.execute = AsyncMock(
        return_value=OpsMetricsDTO(
            payload={
                "request_latency_ms_avg": 1.5,
                "error_rate": 0.0,
                "throughput_per_minute": 10.0,
                "cache_hit_ratio": 0.8,
                "job_duration_ms_avg": 2.0,
                "request_count": 10,
                "error_count": 0,
                "cache_hits": 8,
                "cache_misses": 2,
                "job_count": 1,
                "collected_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    application.dependency_overrides[get_version_service] = lambda: mock_version
    application.dependency_overrides[get_health_service] = lambda: mock_health
    application.dependency_overrides[get_ops_metrics_uc] = lambda: mock_metrics_uc
    return application


@pytest.mark.unit
class TestVersionEndpoint:
    def test_version_returns_metadata(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "QuantForg"
        assert body["version"] == "0.1.0"
        assert body["environment"] == "testing"
        assert body["api_prefix"] == "/api/v1"


@pytest.mark.unit
class TestHealthEndpoints:
    def test_liveness(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_readiness(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_healthz_and_ready_aliases(self) -> None:
        client = TestClient(_build_test_app())
        for path in ("/", "/health", "/healthz", "/ready", "/health/live"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json()["status"] == "ok", path

    def test_metrics_requires_auth(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/metrics")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "missing_token"

    def test_health_status_detailed(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/health/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert len(body["dependencies"]) == 2

    def test_health_unhealthy_returns_200_by_default(self) -> None:
        application = _build_test_app()
        mock_health = MagicMock(spec=HealthService)
        mock_health.check = AsyncMock(
            return_value=HealthReport(
                status=HealthStatus.UNHEALTHY,
                version="0.1.0",
                environment="testing",
                dependencies=[
                    DependencyStatus(
                        name="postgres",
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=5.0,
                    ),
                ],
            )
        )
        application.dependency_overrides[get_health_service] = lambda: mock_health
        client = TestClient(application)
        response = client.get("/api/v1/health/status")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
