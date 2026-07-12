"""Unit tests for application service façades and legacy health/version paths."""

from __future__ import annotations

import pytest

from app.application.dto.health import HealthStatus
from app.application.services.health_service import HealthService
from app.application.services.version_service import VersionService
from app.application.use_cases.get_health import GetHealthUseCase
from app.application.use_cases.get_version import GetVersionUseCase
from tests.unit.fakes import FakeAppInfo


class _AlwaysHealthy:
    @property
    def name(self) -> str:
        return "mock-ok"

    async def check(self) -> bool:
        return True


class _AlwaysUnhealthy:
    @property
    def name(self) -> str:
        return "mock-fail"

    async def check(self) -> bool:
        return False


@pytest.mark.unit
class TestVersionService:
    def test_get_version(self) -> None:
        app_info = FakeAppInfo()
        service = VersionService(use_case=GetVersionUseCase(app_info=app_info))
        info = service.get_version()
        assert info.name == app_info.app_name
        assert info.version == app_info.app_version
        assert info.environment == "testing"


@pytest.mark.unit
class TestHealthService:
    @pytest.mark.asyncio
    async def test_all_healthy(self) -> None:
        use_case = GetHealthUseCase(
            app_info=FakeAppInfo(),
            probes=(_AlwaysHealthy(),),
        )
        service = HealthService(use_case=use_case)
        report = await service.check()
        assert report.status == HealthStatus.HEALTHY
        assert report.dependencies[0].name == "mock-ok"

    @pytest.mark.asyncio
    async def test_unhealthy_dependency(self) -> None:
        use_case = GetHealthUseCase(
            app_info=FakeAppInfo(),
            probes=(_AlwaysHealthy(), _AlwaysUnhealthy()),
        )
        service = HealthService(use_case=use_case)
        report = await service.check()
        assert report.status == HealthStatus.UNHEALTHY
