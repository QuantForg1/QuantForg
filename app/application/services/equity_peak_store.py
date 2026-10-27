"""Durable equity high-water mark for the overall drawdown halt.

The mark is one row in Postgres and does not store an account login.
A missing or unreadable mark is untrusted. The owner check fails closed
only after the owner has saved a nonzero drawdown halt.
"""

from __future__ import annotations

import os
from decimal import Decimal
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_MEMORY_PEAK: Decimal | None = None
_FORCED_DOWN = False

_CREATE_PEAK = """
CREATE TABLE IF NOT EXISTS public.account_equity_peak (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    peak_equity NUMERIC NOT NULL,
    observed_equity NUMERIC NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_PEAK_LOCKDOWN = """
DO $lock$
BEGIN
  EXECUTE 'ALTER TABLE public.account_equity_peak ENABLE ROW LEVEL SECURITY';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.account_equity_peak FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.account_equity_peak FROM authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT ALL ON TABLE public.account_equity_peak TO service_role';
  END IF;
END
$lock$;
"""

_UPSERT_PEAK = """
INSERT INTO public.account_equity_peak (id, peak_equity, observed_equity, updated_at)
VALUES (1, $1, $1, NOW())
ON CONFLICT (id) DO UPDATE
SET peak_equity = GREATEST(
    public.account_equity_peak.peak_equity,
    EXCLUDED.peak_equity
),
    observed_equity = EXCLUDED.observed_equity,
    updated_at = NOW()
RETURNING peak_equity
"""


def reset_equity_peak_for_tests() -> None:
    global _MEMORY_PEAK, _FORCED_DOWN
    with _LOCK:
        _MEMORY_PEAK = None
        _FORCED_DOWN = False


def force_equity_peak_unavailable_for_tests(down: bool) -> None:
    global _FORCED_DOWN
    with _LOCK:
        _FORCED_DOWN = down


def _testing() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _memory_observe(equity: Decimal) -> tuple[Decimal | None, bool]:
    global _MEMORY_PEAK
    with _LOCK:
        if _FORCED_DOWN:
            return None, False
        current = equity if _MEMORY_PEAK is None else max(_MEMORY_PEAK, equity)
        _MEMORY_PEAK = current
        return current, True


def ensure_equity_peak_schema() -> None:
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
        execute,
    )

    if not direct_postgres_available():
        return
    execute(_CREATE_PEAK)
    execute(_PEAK_LOCKDOWN)


def observe_equity_peak(equity: Decimal) -> tuple[Decimal | None, bool]:
    """Return ``(peak, trusted)``. Untrusted means the halt must fail closed."""
    try:
        observed = Decimal(str(equity))
    except Exception:
        return None, False
    if observed <= 0 or _FORCED_DOWN:
        return None, False
    # Tests stay on the memory mark. A unit run must not write the live peak.
    if _testing():
        return _memory_observe(observed)
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
        fetch,
    )

    if not direct_postgres_available():
        return None, False
    try:
        ensure_equity_peak_schema()
        rows: list[dict[str, Any]] = fetch(_UPSERT_PEAK, observed)
    except Exception as exc:
        logger.warning("equity_peak_persist_failed", error_type=type(exc).__name__)
        return None, False
    if not rows:
        return None, False
    try:
        peak = Decimal(str(rows[0].get("peak_equity")))
    except Exception:
        return None, False
    if peak <= 0:
        return None, False
    return peak, True
