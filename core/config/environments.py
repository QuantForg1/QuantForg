"""Environment-specific settings factories.

These helpers produce :class:`~core.config.settings.Settings` instances
pre-tuned for a given deployment target. Prefer environment variables for
overrides; these factories only set safe defaults.
"""

from __future__ import annotations

from core.config.settings import AppEnvironment, Settings


def development_settings(**overrides: object) -> Settings:
    """Settings optimised for local development."""
    defaults: dict[str, object] = {
        "app_env": AppEnvironment.DEVELOPMENT,
        "debug": True,
        "reload": True,
        "log_level": "DEBUG",
        "log_format": "console",
        "log_json": False,
        "postgres_echo": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def production_settings(**overrides: object) -> Settings:
    """Settings optimised for production deployments.

    Callers must supply strong ``secret_key`` and ``postgres_password``
    values; the base model validator will reject insecure defaults.
    """
    defaults: dict[str, object] = {
        "app_env": AppEnvironment.PRODUCTION,
        "debug": False,
        "reload": False,
        "log_level": "INFO",
        "log_format": "json",
        "log_json": True,
        "postgres_echo": False,
        "workers": 4,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def testing_settings(**overrides: object) -> Settings:
    """Settings optimised for automated test runs."""
    defaults: dict[str, object] = {
        "app_env": AppEnvironment.TESTING,
        "debug": True,
        "reload": False,
        "log_level": "WARNING",
        "log_format": "console",
        "log_json": False,
        "postgres_echo": False,
        "postgres_db": "quantforg_test",
        "secret_key": "test-secret-key-that-is-long-enough-for-validation-32chars",
        # Keep unit tests isolated from developer machine .env secrets.
        "supabase_url": "",
        "supabase_publishable_key": None,
        "supabase_anon_key": None,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type]
