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

    def test_production_forces_reload_and_debug_off(self) -> None:
        """Platform-synced RELOAD/DEBUG must not crash production."""
        settings = production_settings(
            debug=True,
            reload=True,
            secret_key="a-real-production-secret-key-with-enough-entropy-here",
            postgres_password="a-real-production-password-here",
        )
        assert settings.debug is False
        assert settings.reload is False

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

    def test_database_url_strips_sslmode_and_enables_ssl(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            database_url_override=(
                "postgresql://user:pass@db.example.supabase.co:5432/postgres"
                "?sslmode=require&channel_binding=require"
            ),
        )
        assert "sslmode" not in settings.database_url
        assert "channel_binding" not in settings.database_url
        assert "ssl" in settings.asyncpg_connect_args

    def test_supabase_db_password_composes_pooler_dsn(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            supabase_url="https://abcdef.supabase.co",
            supabase_db_password="s3cret",  # type: ignore[arg-type]
        )
        assert "postgres.abcdef" in settings.database_url
        assert "pooler.supabase.com" in settings.database_url
        assert "ssl" in settings.asyncpg_connect_args

    def test_production_accepts_database_url_without_postgres_password(
        self,
    ) -> None:
        settings = production_settings(
            secret_key="a-real-production-secret-key-with-enough-entropy-here",
            database_url_override="postgresql://u:p@host:5432/db",
        )
        assert "postgresql+asyncpg://" in settings.database_url

    def test_redis_url_format(self) -> None:
        settings = testing_settings()
        assert settings.redis_url.startswith("redis://")

    def test_redis_url_from_override(self) -> None:
        settings = testing_settings(
            redis_url_override="rediss://:secret@redis.example:6380/1",
        )
        assert settings.redis_url == "rediss://:secret@redis.example:6380/1"

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

    def test_supabase_not_configured_by_default(self) -> None:
        settings = testing_settings()
        assert settings.supabase_configured is False
        assert settings.supabase_api_key is None

    def test_supabase_prefers_publishable_key(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="sb_publishable_test",  # type: ignore[arg-type]
            supabase_anon_key="eyJlegacy",  # type: ignore[arg-type]
        )
        assert settings.supabase_configured is True
        assert settings.supabase_api_key == "sb_publishable_test"

    def test_supabase_falls_back_to_anon_key(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            supabase_url="https://example.supabase.co",
            supabase_publishable_key=None,  # type: ignore[arg-type]
            supabase_anon_key="eyJanon",  # type: ignore[arg-type]
        )
        assert settings.supabase_configured is True
        assert settings.supabase_api_key == "eyJanon"

    def test_empty_allowed_hosts_becomes_wildcard(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            allowed_hosts=[],  # type: ignore[arg-type]
        )
        assert settings.allowed_hosts == ["*"]

    def test_production_rejects_wildcard_hosts(self) -> None:
        settings = production_settings(
            secret_key="a-real-production-secret-key-with-enough-entropy-here",
            postgres_password="a-real-production-password-here",
            allowed_hosts=["*"],  # type: ignore[arg-type]
            railway_public_domain="quantforg-production.up.railway.app",
        )
        assert "*" not in settings.allowed_hosts
        assert "quantforg-production.up.railway.app" in settings.allowed_hosts
        assert ".up.railway.app" in settings.allowed_hosts
        assert settings.execution_enabled is False
        assert settings.docs_enabled is False
        assert "https://quantforg-production.up.railway.app" in settings.cors_origins

    def test_cors_allowed_origins_alias(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            cors_origins="https://app.example.com",  # type: ignore[arg-type]
        )
        assert settings.cors_origins == ["https://app.example.com"]

    def test_environment_alias_maps_to_app_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv("APP_ENV", raising=False)
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
        )
        assert settings.app_env == AppEnvironment.STAGING

    def test_auth_redirect_defaults(self) -> None:
        settings = testing_settings()
        assert "auth/callback" in settings.auth_redirect_url
        assert settings.auth_oauth_enabled is True
