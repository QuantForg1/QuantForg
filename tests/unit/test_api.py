"""Unit tests for API endpoints that do not require live infrastructure.

Health endpoints that probe Postgres/Redis are covered in integration tests.
Version and liveness are pure and tested here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.health import DependencyStatus, HealthReport, HealthStatus
from app.application.dto.version import VersionInfo
from app.application.services.health_service import HealthService
from app.application.services.version_service import VersionService
from app.presentation.dependencies.services import (
    get_health_service,
    get_version_service,
)
from app.presentation.routers import health, version


def _build_test_app() -> FastAPI:
    """Minimal FastAPI app with only foundation routers and mocked services."""
    application = FastAPI()
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(version.router, prefix="/api/v1")

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

    application.dependency_overrides[get_version_service] = lambda: mock_version
    application.dependency_overrides[get_health_service] = lambda: mock_health
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
        assert response.json()["status"] == "alive"

    def test_health_healthy(self) -> None:
        client = TestClient(_build_test_app())
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert len(body["dependencies"]) == 2

    def test_health_unhealthy_returns_503(self) -> None:
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
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"
