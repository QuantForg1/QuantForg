"""HTTP API routers."""

from app.presentation.routers import (
    auth,
    health,
    notifications,
    organizations,
    profile,
    settings,
    version,
)

__all__ = [
    "auth",
    "health",
    "notifications",
    "organizations",
    "profile",
    "settings",
    "version",
]
