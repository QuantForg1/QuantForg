"""Service dependency providers."""

from __future__ import annotations

from app.application.services.health_service import HealthService
from app.application.services.version_service import VersionService
from app.application.use_cases.get_health import GetHealthUseCase
from app.application.use_cases.get_version import GetVersionUseCase
from app.infrastructure.cache.health import RedisHealthCheck
from app.infrastructure.config.app_info import SettingsAppInfo
from app.infrastructure.database.health import PostgresHealthCheck
from core.config.settings import Settings, get_settings
from core.di.container import get_container


def get_settings_dependency() -> Settings:
    """Provide the cached application settings singleton."""
    return get_settings()


def get_health_service() -> HealthService:
    """Build a :class:`HealthService` wired to live infrastructure probes."""
    container = get_container()
    app_info = SettingsAppInfo(settings=container.settings)
    probes = (
        PostgresHealthCheck(database=container.database),
        RedisHealthCheck(redis=container.require_redis()),
    )
    use_case = GetHealthUseCase(app_info=app_info, probes=probes)
    return HealthService(use_case=use_case)


def get_version_service() -> VersionService:
    """Provide a :class:`VersionService` bound to current settings."""
    app_info = SettingsAppInfo(settings=get_settings())
    use_case = GetVersionUseCase(app_info=app_info)
    return VersionService(use_case=use_case)
