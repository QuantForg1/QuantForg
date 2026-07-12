"""Application configuration system.

Settings are loaded from environment variables and optional ``.env`` files
via Pydantic Settings. Environment-specific subclasses (development,
production, testing) enforce appropriate defaults and validation rules.
"""

from core.config.settings import (
    AppEnvironment,
    Settings,
    get_settings,
)

__all__ = [
    "AppEnvironment",
    "Settings",
    "get_settings",
]
