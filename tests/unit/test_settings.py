"""Unit tests for configuration and settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config.environments import (
    development_settings,
    production_settings,
    testing_settings,
)
from core.config.settings import AppEnvironment, Settings, get_settings


@pytest.mark.unit
class TestSettings:
    def test_default_development_values(self) -> None:
        settings = development_settings(
            secret_key="dev-secret-key-that-is-long-enough-for-validation-32",
        )
        assert settings.app_env == AppEnvironment.DEVELOPMENT
        assert settings.debug is True
        assert settings.log_format == "console"

    def test_testing_settings(self) -> None:
        settings = testing_settings()
        assert settings.app_env == AppEnvironment.TESTING
        assert settings.postgres_db == "quantforg_test"

    def test_production_rejects_debug(self) -> None:
        with pytest.raises(ValidationError):
            production_settings(
                debug=True,
                secret_key="a-real-production-secret-key-with-enough-entropy-here",
                postgres_password="a-real-production-password-here",
            )

    def test_production_rejects_insecure_secret(self) -> None:
        with pytest.raises(ValidationError):
            production_settings(
                secret_key="change-me-to-a-long-random-secret-key-at-least-64-chars",
                postgres_password="a-real-production-password-here",
            )

    def test_database_url_format(self) -> None:
        settings = testing_settings()
        assert settings.database_url.startswith("postgresql+asyncpg://")
        assert "quantforg_test" in settings.database_url

    def test_redis_url_format(self) -> None:
        settings = testing_settings()
        assert settings.redis_url.startswith("redis://")

    def test_comma_separated_cors_origins(self) -> None:
        settings = Settings(
            cors_origins="http://a.com,http://b.com",  # type: ignore[arg-type]
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
        )
        assert settings.cors_origins == ["http://a.com", "http://b.com"]

    def test_get_settings_is_cached(self) -> None:
        get_settings.cache_clear()
        a = get_settings()
        b = get_settings()
        assert a is b
        get_settings.cache_clear()

    def test_invalid_log_level_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Settings(
                log_level="VERBOSE",
                secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
                app_env=AppEnvironment.TESTING,
            )
