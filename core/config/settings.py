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
    AliasChoices,
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
        populate_by_name=True,
    )

    # -- Application ----------------------------------------------------------
    app_name: Annotated[str, Field(description="Human-readable application name")] = (
        "QuantForg"
    )
    app_version: Annotated[str, Field(description="Semantic version string")] = "1.0.0"
    app_env: Annotated[
        AppEnvironment,
        Field(
            description="Runtime environment selector",
            validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT", "app_env"),
        ),
    ] = AppEnvironment.DEVELOPMENT
    debug: Annotated[bool, Field(description="Enable debug mode")] = False
    api_prefix: Annotated[str, Field(description="URL prefix for all API routes")] = (
        "/api/v1"
    )
    allowed_hosts: Annotated[
        list[str],
        NoDecode,
        Field(
            description=(
                "Trusted hostnames for Host header validation "
                "(ALLOWED_HOSTS). Production never uses '*'; "
                "defaults derive from RAILWAY_PUBLIC_DOMAIN."
            ),
            validation_alias=AliasChoices("ALLOWED_HOSTS", "allowed_hosts"),
        ),
    ] = ["*"]
    cors_origins: Annotated[
        list[str],
        NoDecode,
        Field(
            description=(
                "Allowed CORS origins (CORS_ORIGINS / CORS_ALLOWED_ORIGINS). "
                "Wildcards are stripped; production uses an explicit allowlist."
            ),
            validation_alias=AliasChoices(
                "CORS_ORIGINS",
                "CORS_ALLOWED_ORIGINS",
                "cors_origins",
            ),
        ),
    ] = ["http://localhost:3000", "http://localhost:8000"]
    docs_enabled: Annotated[
        bool,
        Field(description="Expose /docs, /redoc, and /openapi.json"),
    ] = True
    railway_public_domain: Annotated[
        str | None,
        Field(
            default=None,
            description="Railway public hostname (RAILWAY_PUBLIC_DOMAIN)",
            validation_alias=AliasChoices(
                "RAILWAY_PUBLIC_DOMAIN", "railway_public_domain"
            ),
        ),
    ] = None

    # -- Server ---------------------------------------------------------------
    host: Annotated[str, Field(description="Bind address")] = "0.0.0.0"
    port: Annotated[int, Field(ge=1, le=65535, description="Bind port")] = 8000
    workers: Annotated[int, Field(ge=1, description="Uvicorn worker count")] = 1
    reload: Annotated[bool, Field(description="Enable auto-reload (dev only)")] = False
    # When False (default), /health and /health/ready return HTTP 200 even if
    # optional/critical deps are degraded — required for Railway edge probes.
    health_http_strict: Annotated[
        bool,
        Field(
            description=(
                "If True, unhealthy dependencies yield HTTP 503 on /health and "
                "/health/ready. If False, always HTTP 200 with status in body."
            )
        ),
    ] = False

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
    postgres_ssl: Annotated[
        bool | None,
        Field(
            description=(
                "Force TLS for Postgres (asyncpg). None = auto from DATABASE_URL "
                "sslmode / known managed hosts"
            )
        ),
    ] = None
    database_url_override: Annotated[
        str | None,
        Field(
            default=None,
            description="Full Postgres DSN from the platform (DATABASE_URL)",
            validation_alias=AliasChoices(
                "DATABASE_URL",
                "SUPABASE_DB_URL",
                "database_url_override",
            ),
        ),
    ] = None

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
    supabase_db_password: Annotated[
        SecretStr | None,
        Field(
            default=None,
            description=(
                "Supabase database password used to compose DATABASE_URL when "
                "DATABASE_URL is unset (pooler session mode)"
            ),
            validation_alias=AliasChoices(
                "SUPABASE_DB_PASSWORD",
                "supabase_db_password",
            ),
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
    redis_url_override: Annotated[
        str | None,
        Field(
            default=None,
            description="Full Redis DSN from the platform (REDIS_URL)",
            validation_alias=AliasChoices("REDIS_URL", "redis_url_override"),
        ),
    ] = None

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
        if value is None:
            return []
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            # Empty ALLOWED_HOSTS="" must not become [] (rejects every Host).
            return items
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
        """Harden production: coerce unsafe toggles; reject insecure secrets."""
        from urllib.parse import urlparse

        if self.app_env == AppEnvironment.PRODUCTION:
            # Platform dashboards often sync RELOAD=true / DEBUG=true from .env
            # templates. Coerce instead of crashing the container.
            if self.reload:
                object.__setattr__(self, "reload", False)
            if self.debug:
                object.__setattr__(self, "debug", False)
            # Live trading must never ship enabled.
            if self.execution_enabled:
                object.__setattr__(self, "execution_enabled", False)
            insecure_markers = ("change-me", "dev_password", "secret-key-at-least")
            secret = self.secret_key.get_secret_value()
            if any(marker in secret for marker in insecure_markers):
                msg = "SECRET_KEY must be replaced with a strong production value"
                raise ValueError(msg)
            # Platforms often inject DATABASE_URL only; skip composed password check.
            dsn = (self.database_url_override or "").strip()
            if not dsn:
                password = self.postgres_password.get_secret_value()
                if any(marker in password for marker in insecure_markers):
                    msg = "POSTGRES_PASSWORD must be replaced in production"
                    raise ValueError(msg)

        domain = (self.railway_public_domain or "").strip()
        hosts = [h.strip() for h in self.allowed_hosts if h and h.strip()]

        # Production: never leave Host validation as a bare wildcard.
        railway_probe_hosts = (
            ".up.railway.app",
            "healthcheck.railway.app",
            "localhost",
            "127.0.0.1",
        )
        if self.app_env == AppEnvironment.PRODUCTION:
            hosts = [h for h in hosts if h != "*"]
            if domain and domain not in hosts:
                hosts = [domain, *hosts]
            if not hosts:
                hosts = [domain] if domain else []
                hosts.extend(railway_probe_hosts)
            else:
                for probe in railway_probe_hosts:
                    if probe not in hosts:
                        hosts.append(probe)
        else:
            # Empty or missing hosts reject every request behind Railway → edge 502.
            if not hosts:
                hosts = ["*"]
            if domain and "*" not in hosts and domain not in hosts:
                hosts = [*hosts, domain]

        if hosts != self.allowed_hosts:
            object.__setattr__(self, "allowed_hosts", hosts)

        # CORS: strip wildcards; production seeds from Railway / auth redirect.
        origins = [o.strip() for o in self.cors_origins if o and o.strip() and o != "*"]
        if self.app_env == AppEnvironment.PRODUCTION:
            if domain:
                railway_origin = f"https://{domain}"
                if railway_origin not in origins:
                    origins.append(railway_origin)
            redirect = (self.auth_redirect_url or "").strip()
            if redirect:
                parsed = urlparse(redirect)
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    if origin not in origins:
                        origins.append(origin)
        if origins != self.cors_origins:
            object.__setattr__(self, "cors_origins", origins)

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
        """Async SQLAlchemy connection URL (asyncpg driver), query-cleaned."""
        return self._asyncpg_dsn_and_ssl()[0]

    def _asyncpg_dsn_and_ssl(self) -> tuple[str, bool]:
        """Normalize DSN for asyncpg and decide whether TLS is required."""
        from urllib.parse import quote

        override = (self.database_url_override or "").strip()
        if not override and self.supabase_db_password is not None:
            password = self.supabase_db_password.get_secret_value().strip()
            ref = self._supabase_project_ref
            if password and ref:
                override = (
                    f"postgresql://postgres.{ref}:{quote(password, safe='')}"
                    f"@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
                )
        if override:
            raw = self._as_asyncpg_url(override)
        else:
            password = self.postgres_password.get_secret_value()
            raw = (
                f"postgresql+asyncpg://{self.postgres_user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self._strip_libpq_ssl_params(raw)

    @property
    def _supabase_project_ref(self) -> str | None:
        """Extract project ref from ``SUPABASE_URL`` when present."""
        from urllib.parse import urlparse

        raw = (self.supabase_url or "").strip()
        if not raw:
            return None
        host = (urlparse(raw).hostname or "").lower()
        # <ref>.supabase.co
        if host.endswith(".supabase.co"):
            return host.split(".", 1)[0] or None
        return None

    def _strip_libpq_ssl_params(self, url: str) -> tuple[str, bool]:
        """Remove libpq-only query params; return (clean_url, use_ssl)."""
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        sslmode = (query.pop("sslmode", "") or "").lower()
        query.pop("channel_binding", None)
        query.pop("sslrootcert", None)
        query.pop("sslcert", None)
        query.pop("sslkey", None)

        host = (parsed.hostname or "").lower()
        supabase_host = "supabase.co" in host or "supabase.com" in host
        private_host = host.endswith(".railway.internal") or host in {
            "localhost",
            "127.0.0.1",
        }

        if self.postgres_ssl is True:
            use_ssl = True
        elif self.postgres_ssl is False:
            use_ssl = False
        elif sslmode in {"require", "verify-ca", "verify-full"}:
            use_ssl = True
        elif sslmode in {"disable", "allow", "prefer"}:
            use_ssl = False
        else:
            # Supabase public/pooler endpoints expect TLS (often with a
            # non-standard chain). Private Railway hosts stay cleartext.
            use_ssl = supabase_host and not private_host

        cleaned = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query),
                parsed.fragment,
            )
        )
        return cleaned, use_ssl

    @property
    def asyncpg_connect_args(self) -> dict[str, Any]:
        """Connect args for ``create_async_engine`` (SSL + pooler-safe cache)."""
        import ssl
        from urllib.parse import urlparse

        url, use_ssl = self._asyncpg_dsn_and_ssl()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port or 5432
        args: dict[str, Any] = {}

        # PgBouncer (Supabase pooler / transaction mode) rejects prepared
        # statements — disable asyncpg's statement cache for those targets.
        if port == 6543 or "pooler.supabase.com" in host:
            args["statement_cache_size"] = 0

        if not use_ssl:
            return args

        # Supabase pooler presents a chain that fails default CA verification
        # on many runtimes; encrypt the socket without hostname CA pin.
        if "supabase.co" in host or "supabase.com" in host:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            args["ssl"] = ctx
        else:
            args["ssl"] = True
        return args

    @staticmethod
    def _as_asyncpg_url(url: str) -> str:
        """Normalize platform DSNs to SQLAlchemy asyncpg form."""
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        return url

    @property
    def redis_configured(self) -> bool:
        """True when Redis was explicitly provisioned via ``REDIS_URL``."""
        return bool((self.redis_url_override or "").strip())

    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        override = (self.redis_url_override or "").strip()
        if override:
            return override
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
