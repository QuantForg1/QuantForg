"""UTC-session daily-loss circuit breaker — latch, never raise the cap.

Daily loss remains a hard new-entry lock. This module only:
- measures realized UTC-day P/L the same way Risk Engine does
- arms the plane latch when the current UTC day is over the cap
- clears the latch when the current UTC day is back under the cap
- uses ITE MAX_DAILY_LOSS_PCT as the single hard cap

It does not bypass Risk or force trades.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def utc_session_day(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).date().isoformat()


def utc_daily_loss_base(
    *,
    equity: Decimal,
    balance: Decimal | None = None,
) -> tuple[Decimal, str]:
    """Denominator for daily-loss %. Balance if >0, else equity. Never deposits."""
    eq = Decimal(str(equity or 0))
    bal = Decimal(str(balance)) if balance is not None else Decimal("0")
    if bal > 0:
        return bal, "balance"
    return eq, "equity"


def utc_daily_loss_pct(
    *,
    daily_pnl: Decimal,
    equity: Decimal,
    balance: Decimal | None = None,
) -> Decimal:
    """Percent loss for the current UTC session. Matches RiskEngine._loss_pct."""
    pnl = Decimal(str(daily_pnl or 0))
    base, _name = utc_daily_loss_base(equity=equity, balance=balance)
    if base <= 0 or pnl >= 0:
        return Decimal("0")
    return ((-pnl) / base * Decimal("100")).quantize(Decimal("0.01"))


def utc_daily_loss_exceeded(
    *,
    daily_pnl: Decimal,
    equity: Decimal,
    balance: Decimal | None,
    max_daily_loss_pct: Decimal,
) -> bool:
    cap = Decimal(str(max_daily_loss_pct or 0))
    pct = utc_daily_loss_pct(daily_pnl=daily_pnl, equity=equity, balance=balance)
    return pct > cap > 0


def utc_daily_loss_resets_at(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    nxt = moment.astimezone(UTC).date() + timedelta(days=1)
    return datetime(nxt.year, nxt.month, nxt.day, tzinfo=UTC).strftime(
        "%Y-%m-%dT00:00:00Z"
    )


def sync_utc_daily_loss_lock(
    plane: Any | None,
    *,
    daily_pnl: Decimal,
    equity: Decimal,
    balance: Decimal | None,
    max_daily_loss_pct: Decimal,
    trusted: bool = True,
    now: datetime | None = None,
    floating_pnl: Decimal | None = None,
) -> dict[str, Any]:
    """Arm or clear the plane latch from current UTC-day P/L.

    Untrusted P/L (deals unavailable) fail-closes: keep/arm the lock.
    """
    cap = Decimal(str(max_daily_loss_pct or 0))
    pct = utc_daily_loss_pct(daily_pnl=daily_pnl, equity=equity, balance=balance)
    session = utc_session_day(now)
    resets = utc_daily_loss_resets_at(now)
    exceeded = True if not trusted else utc_daily_loss_exceeded(
        daily_pnl=daily_pnl,
        equity=equity,
        balance=balance,
        max_daily_loss_pct=cap,
    )
    prior = bool(getattr(plane, "daily_loss_exceeded", False)) if plane is not None else False
    changed = False
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    if plane is not None:
        if exceeded and not prior:
            plane.flag_daily_loss(now=now)
            changed = True
            logger.warning(
                "daily_loss_lock_armed",
                daily_loss_pct=str(pct),
                limit_pct=str(cap),
                session_day=session,
            )
        elif not exceeded and prior:
            clear = getattr(plane, "clear_daily_loss", None)
            if callable(clear):
                clear(now=now, reason="utc_session_under_cap")
                changed = True
            else:
                plane.daily_loss_exceeded = False
                if hasattr(plane, "daily_loss_armed_at"):
                    plane.daily_loss_armed_at = None
                changed = True
            logger.warning(
                "daily_loss_lock_cleared",
                daily_loss_pct=str(pct),
                limit_pct=str(cap),
                session_day=session,
            )
            try:
                from app.domain.institutional_trading.operations.decision_cycle import (
                    note_cycle_event,
                )

                note_cycle_event("daily_loss_cleared")
            except Exception:
                logger.exception("daily_loss_cleared_wakeup_failed")
            try:
                from app.application.services.auto_trading_continuity import (
                    ensure_auto_trading_running,
                )

                ensure_auto_trading_running(
                    plane,
                    reason="daily_loss_lock_cleared",
                )
            except Exception:
                logger.exception("daily_loss_auto_resume_failed")
    base, base_name = utc_daily_loss_base(equity=equity, balance=balance)
    armed_at = getattr(plane, "daily_loss_armed_at", None) if plane is not None else None
    lock_age: int | None = None
    if exceeded and isinstance(armed_at, datetime):
        armed = armed_at if armed_at.tzinfo else armed_at.replace(tzinfo=UTC)
        lock_age = max(0, int((moment - armed.astimezone(UTC)).total_seconds()))
    floating = Decimal(str(floating_pnl or 0)) if floating_pnl is not None else None
    rearm = "LOCKED" if exceeded else "CLEAR"
    if not exceeded and prior and changed:
        rearm = "REARMED"
    return {
        "daily_loss_pct": str(pct),
        "daily_loss_limit_pct": str(cap),
        "daily_loss_lock": "EXCEEDED" if exceeded else "CLEAR",
        "daily_loss_exceeded": bool(exceeded),
        "daily_loss_base": base_name,
        "daily_loss_base_value": str(base),
        "daily_realized_pnl": str(daily_pnl),
        "daily_unrealized_pnl": str(floating) if floating is not None else None,
        "utc_session_date": session,
        "daily_loss_session_day": session,
        "daily_loss_resets_at": resets,
        "daily_pnl": str(daily_pnl),
        "daily_pnl_trusted": bool(trusted),
        "daily_loss_source": "utc_session_deals" if trusted else "fail_closed",
        "history_confidence": "trusted" if trusted else "untrusted_fail_closed",
        "lock_age": lock_age,
        "rearm_state": rearm,
        "lock_changed": changed,
        "source": "utc_session_deals" if trusted else "fail_closed",
    }
