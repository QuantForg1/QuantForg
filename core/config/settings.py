"""Pydantic Settings for QuantForg.

Configuration is the single source of truth for runtime behaviour.
Every setting is typed, validated, and documented. Secrets are never
hard-coded — they must come from the environment or a ``.env`` file.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Root application settings.

    Loaded once at process start and shared via :func:`get_settings`.
    Environment variables take precedence over ``.env`` file values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # -- Application ----------------------------------------------------------
    app_name: Annotated[str, Field(description="Human-readable application name")] = (
        "QuantForg"
    )
    app_version: Annotated[str, Field(description="Semantic version string")] = "1.0.0"
    app_env: Annotated[
        AppEnvironment,
        Field(description="Runtime environment selector"),
    ] = AppEnvironment.DEVELOPMENT
    debug: Annotated[bool, Field(description="Enable debug mode")] = False
    api_prefix: Annotated[str, Field(description="URL prefix for all API routes")] = (
        "/api/v1"
    )
    allowed_hosts: Annotated[
        list[str],
        NoDecode,
        Field(description="Trusted hostnames for Host header validation"),
    ] = ["localhost", "127.0.0.1"]
    cors_origins: Annotated[
        list[str],
        NoDecode,
        Field(description="Allowed CORS origins"),
    ] = ["http://localhost:3000", "http://localhost:8000"]

    # -- Server ---------------------------------------------------------------
    host: Annotated[str, Field(description="Bind address")] = "0.0.0.0"
    port: Annotated[int, Field(ge=1, le=65535, description="Bind port")] = 8000
    workers: Annotated[int, Field(ge=1, description="Uvicorn worker count")] = 1
    reload: Annotated[bool, Field(description="Enable auto-reload (dev only)")] = False

    # -- Logging --------------------------------------------------------------
    log_level: Annotated[
        str,
        Field(description="Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    ] = "INFO"
    log_format: Annotated[
        str,
        Field(description="Log renderer: 'console' or 'json'"),
    ] = "json"
    log_json: Annotated[
        bool,
        Field(description="Force JSON structured logging"),
    ] = True

    # -- PostgreSQL -----------------------------------------------------------
    postgres_host: Annotated[str, Field(description="PostgreSQL hostname")] = (
        "localhost"
    )
    postgres_port: Annotated[
        int, Field(ge=1, le=65535, description="PostgreSQL port")
    ] = 5432
    postgres_user: Annotated[str, Field(description="PostgreSQL username")] = (
        "quantforg"
    )
    postgres_password: Annotated[
        SecretStr, Field(description="PostgreSQL password")
    ] = SecretStr("quantforg_dev_password_change_me")
    postgres_db: Annotated[str, Field(description="PostgreSQL database name")] = (
        "quantforg"
    )
    postgres_pool_size: Annotated[
        int, Field(ge=1, description="SQLAlchemy connection pool size")
    ] = 5
    postgres_max_overflow: Annotated[
        int, Field(ge=0, description="SQLAlchemy pool max overflow")
    ] = 10
    postgres_echo: Annotated[bool, Field(description="Echo SQL statements to log")] = (
        False
    )

    # -- Supabase -------------------------------------------------------------
    supabase_url: Annotated[
        str,
        Field(description="Supabase project URL (https://xxxx.supabase.co)"),
    ] = ""
    supabase_publishable_key: Annotated[
        SecretStr | None,
        Field(description="Supabase publishable API key (preferred)"),
    ] = None
    supabase_anon_key: Annotated[
        SecretStr | None,
        Field(description="Supabase legacy anon JWT (fallback)"),
    ] = None
    supabase_service_role_key: Annotated[
        SecretStr | None,
        Field(
            description=(
                "Supabase service-role key for server-side profile sync "
                "(never expose to clients)"
            )
        ),
    ] = None
    auth_redirect_url: Annotated[
        str,
        Field(description="Default redirect URL for OAuth and password reset"),
    ] = "http://localhost:3000/auth/callback"
    auth_oauth_enabled: Annotated[
        bool,
        Field(description="Expose Google/GitHub OAuth endpoints"),
    ] = True

    # -- Redis ----------------------------------------------------------------
    redis_host: Annotated[str, Field(description="Redis hostname")] = "localhost"
    redis_port: Annotated[int, Field(ge=1, le=65535, description="Redis port")] = 6379
    redis_db: Annotated[int, Field(ge=0, description="Redis database index")] = 0
    redis_password: Annotated[
        SecretStr | None, Field(description="Redis password (optional)")
    ] = None
    redis_ssl: Annotated[bool, Field(description="Use TLS for Redis")] = False
    redis_pool_size: Annotated[
        int, Field(ge=1, description="Redis connection pool size")
    ] = 10

    # -- Security -------------------------------------------------------------
    secret_key: Annotated[
        SecretStr,
        Field(
            min_length=32,
            description="Application secret key for signing tokens",
        ),
    ] = SecretStr("change-me-to-a-long-random-secret-key-at-least-64-chars")
    encryption_key_version: Annotated[
        int,
        Field(ge=1, description="Active AES-256-GCM credential key version"),
    ] = 1
    credential_encryption_previous_keys: Annotated[
        list[SecretStr],
        NoDecode,
        Field(
            default_factory=list,
            description="Prior credential encryption secrets for key rotation",
        ),
    ]
    access_token_expire_minutes: Annotated[
        int, Field(ge=1, description="JWT access token lifetime in minutes")
    ] = 30
    algorithm: Annotated[str, Field(description="JWT signing algorithm")] = "HS256"

    # -- Observability --------------------------------------------------------
    health_check_timeout_seconds: Annotated[
        float, Field(gt=0, description="Health check probe timeout")
    ] = 5.0

    # -- MT5 Adapter (connection layer) --------------------------------------
    mt5_enabled: Annotated[
        bool,
        Field(description="Register the MT5 connection-layer adapter"),
    ] = True
    mt5_use_mock: Annotated[
        bool,
        Field(
            description=(
                "Use MockMT5Client instead of a live MetaTrader5 terminal "
                "(required for CI / non-Windows)"
            )
        ),
    ] = True
    mt5_terminal_path: Annotated[
        str,
        Field(description="Optional path to the MetaTrader 5 terminal"),
    ] = ""
    mt5_connect_timeout_seconds: Annotated[
        float,
        Field(gt=0, description="MT5 connect timeout in seconds"),
    ] = 60.0

    # -- Execution Gateway (DISABLED by default) -----------------------------
    execution_enabled: Annotated[
        bool,
        Field(
            description=(
                "Allow MT5 Execution Gateway order_send. "
                "DISABLED by default — never enable in production without review"
            )
        ),
    ] = False

    # -- Persistence ----------------------------------------------------------
    durable_persistence: Annotated[
        bool,
        Field(
            description=(
                "Use SQLAlchemy Postgres Unit of Work factories when not "
                "testing. Set False to force in-memory factories. "
                "Testing env always uses memory."
            )
        ),
    ] = True

    # -- Validators -----------------------------------------------------------

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: Any) -> list[str]:
        """Accept comma-separated strings or native lists from the environment."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        msg = f"Expected str or list, got {type(value).__name__}"
        raise TypeError(msg)

    @field_validator("credential_encryption_previous_keys", mode="before")
    @classmethod
    def _parse_previous_encryption_keys(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        msg = f"Expected str or list, got {type(value).__name__}"
        raise TypeError(msg)

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            msg = f"log_level must be one of {sorted(allowed)}, got '{value}'"
            raise ValueError(msg)
        return normalized

    @field_validator("log_format")
    @classmethod
    def _normalize_log_format(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"console", "json"}:
            msg = f"log_format must be 'console' or 'json', got '{value}'"
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Settings:
        """Reject insecure defaults when running in production."""
        if self.app_env == AppEnvironment.PRODUCTION:
            if self.debug:
                msg = "DEBUG must be False in production"
                raise ValueError(msg)
            if self.reload:
                msg = "RELOAD must be False in production"
                raise ValueError(msg)
            insecure_markers = ("change-me", "dev_password", "secret-key-at-least")
            secret = self.secret_key.get_secret_value()
            if any(marker in secret for marker in insecure_markers):
                msg = "SECRET_KEY must be replaced with a strong production value"
                raise ValueError(msg)
            password = self.postgres_password.get_secret_value()
            if any(marker in password for marker in insecure_markers):
                msg = "POSTGRES_PASSWORD must be replaced in production"
                raise ValueError(msg)
        return self

    # -- Computed properties --------------------------------------------------

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnvironment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnvironment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self.app_env == AppEnvironment.TESTING

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg driver)."""
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        scheme = "rediss" if self.redis_ssl else "redis"
        auth = ""
        if self.redis_password is not None:
            secret = self.redis_password.get_secret_value()
            if secret:
                auth = f":{secret}@"
        return f"{scheme}://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def supabase_configured(self) -> bool:
        """Return True when URL and at least one API key are present."""
        return bool(self.supabase_url.strip()) and self.supabase_api_key is not None

    @property
    def supabase_api_key(self) -> str | None:
        """Prefer publishable key; fall back to legacy anon JWT."""
        if self.supabase_publishable_key is not None:
            value = self.supabase_publishable_key.get_secret_value().strip()
            if value:
                return value
        if self.supabase_anon_key is not None:
            value = self.supabase_anon_key.get_secret_value().strip()
            if value:
                return value
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings singleton.

    Call ``get_settings.cache_clear()`` in tests to reload configuration.
    """
    return Settings()
