"""Platform switch for customer (multi-account) LIVE order sending.

Customer LIVE needs every lock open: the env flags
(MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED and MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED)
**and** the active ``platform_risk_policy`` row with
``multi_account_live_enabled = true`` and ``global_emergency_stop = false``.
The database switch is the operator's source of truth. When it cannot be
read, customer LIVE is closed. The owner's own robot path is not affected.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger(__name__)

_TTL_SECONDS = 15.0
_LOCK = threading.Lock()
_CACHE: tuple[float, PlatformLiveSwitch] | None = None
# Tests set this to stand in for the database row.
TEST_OVERRIDE: PlatformLiveSwitch | None = None


@dataclass(frozen=True, slots=True)
class PlatformLiveSwitch:
    enabled: bool
    reason: str | None  # None when enabled

    def to_dict(self) -> dict[str, object]:
        return {"enabled": self.enabled, "reason": self.reason}


def _testing() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _read() -> PlatformLiveSwitch:
    try:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch,
        )

        if not direct_postgres_available():
            return PlatformLiveSwitch(False, "platform_live_switch_unavailable")
        rows = fetch("""
            SELECT multi_account_live_enabled, global_emergency_stop
              FROM public.platform_risk_policy
             WHERE is_active
             LIMIT 1
            """)
    except Exception as exc:
        logger.warning("platform_live_switch_read_failed", error=type(exc).__name__)
        return PlatformLiveSwitch(False, "platform_live_switch_unavailable")
    if not rows:
        return PlatformLiveSwitch(False, "platform_live_policy_missing")
    row = rows[0]
    if bool(row.get("global_emergency_stop")):
        return PlatformLiveSwitch(False, "platform_emergency_stop")
    if not bool(row.get("multi_account_live_enabled")):
        return PlatformLiveSwitch(False, "platform_live_disabled")
    return PlatformLiveSwitch(True, None)


def platform_live_switch(*, refresh: bool = False) -> PlatformLiveSwitch:
    """Current DB switch, cached briefly. Fails closed."""
    global _CACHE
    if TEST_OVERRIDE is not None:
        return TEST_OVERRIDE
    if _testing():
        # No database in unit tests: closed unless a test opens it.
        return PlatformLiveSwitch(False, "platform_live_disabled")
    now = time.monotonic()
    with _LOCK:
        if not refresh and _CACHE is not None and now - _CACHE[0] < _TTL_SECONDS:
            return _CACHE[1]
    value = _read()
    with _LOCK:
        _CACHE = (now, value)
    return value


def reset_for_tests() -> None:
    global _CACHE, TEST_OVERRIDE
    with _LOCK:
        _CACHE = None
    TEST_OVERRIDE = None
