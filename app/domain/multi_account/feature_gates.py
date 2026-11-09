"""Feature gates for multi-account work.

Both gates default closed. LIVE submit additionally requires dispatch.
These helpers never enable trading by themselves — callers must still
pass Safety / Risk / OMS / owner hard ceilings.
"""

from __future__ import annotations

from typing import Any


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def multi_account_dispatch_allowed(settings: Any | None = None) -> bool:
    """True only when durable multi-account dispatch is explicitly enabled."""
    if settings is None:
        from core.config.settings import get_settings

        settings = get_settings()
    return _as_bool(getattr(settings, "multi_account_dispatch_enabled", False))


def multi_account_live_submit_allowed(settings: Any | None = None) -> bool:
    """True only when owner-gated LIVE fan-out is explicitly enabled.

    Requires dispatch as well. Default path keeps the existing singleton
    gateway execution as the sole LIVE submit route.
    """
    if settings is None:
        from core.config.settings import get_settings

        settings = get_settings()
    if not multi_account_dispatch_allowed(settings):
        return False
    return _as_bool(getattr(settings, "multi_account_live_submit_enabled", False))
