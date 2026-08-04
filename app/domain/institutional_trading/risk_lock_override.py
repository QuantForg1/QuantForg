"""Controlled daily-loss lock override for TEST MODE only.

ALLOW_RISK_LOCK_OVERRIDE=true lets Auto Trading continue past the *daily loss*
capital lock while testing. It does not disable the Risk Engine and never
bypasses margin, broker validation, market-closed, invalid volume/stops, or
emergency stop.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

OVERRIDE_REASON = "Testing only"
_DAILY_LOSS_MARKERS = (
    "daily loss",
    "maximum daily loss",
    "daily_loss",
)


def risk_lock_override_enabled(settings: Any | None = None) -> bool:
    """Permanently disabled — production finalization (daily-loss lock always ON)."""
    _ = settings
    return False


def is_daily_loss_lock_reason(reason: str) -> bool:
    """True when a reject reason is specifically the daily-loss capital lock."""
    text = (reason or "").strip().lower()
    if not text:
        return False
    # Never treat weekly/monthly/max drawdown / emergency as daily-loss override.
    if "weekly" in text or "monthly" in text:
        return False
    if "max drawdown" in text or "emergency" in text or "kill" in text:
        return False
    return any(marker in text for marker in _DAILY_LOSS_MARKERS)


def split_daily_loss_reasons(
    reasons: list[str] | tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Return (remaining_reasons, daily_loss_reasons)."""
    remaining: list[str] = []
    daily: list[str] = []
    for raw in reasons:
        text = str(raw or "").strip()
        if not text:
            continue
        if is_daily_loss_lock_reason(text):
            daily.append(text)
        else:
            remaining.append(text)
    return remaining, daily


def apply_daily_loss_lock_override(
    reasons: list[str] | tuple[str, ...],
    *,
    settings: Any | None = None,
    current_daily_loss_pct: Decimal | float | str | None = None,
    log: bool = False,
) -> tuple[list[str], bool]:
    """Strip daily-loss reasons when override is armed.

    Returns (remaining_reasons, did_override).
    """
    remaining, daily = split_daily_loss_reasons(reasons)
    if not daily or not risk_lock_override_enabled(settings):
        return list(reasons), False
    if log:
        log_risk_lock_overridden(
            current_daily_loss_pct=current_daily_loss_pct,
            detail="; ".join(daily),
        )
    return remaining, True


def log_risk_lock_overridden(
    *,
    current_daily_loss_pct: Decimal | float | str | None = None,
    detail: str | None = None,
) -> None:
    """Emit the required operator banner for every overridden trade path."""
    current = (
        str(current_daily_loss_pct) if current_daily_loss_pct is not None else "unknown"
    )
    current_txt = current if current.endswith("%") else f"{current}%"
    lines = [
        "RISK LOCK OVERRIDDEN",
        f"Current Daily Loss: {current_txt}",
        f"Reason: {OVERRIDE_REASON}",
    ]
    if detail:
        lines.append(f"Detail: {detail}")
    logger.warning("\n".join(lines))


def risk_lock_override_status(settings: Any | None = None) -> dict[str, Any]:
    """Payload for Auto Trading dashboard TEST MODE banner."""
    enabled = risk_lock_override_enabled(settings)
    return {
        "enabled": enabled,
        "banner": enabled,
        "test_mode": enabled,
        "message": (
            "Daily loss lock overridden." if enabled else "Risk lock override inactive"
        ),
        "reason": OVERRIDE_REASON if enabled else None,
        "overrides": ["daily_loss"] if enabled else [],
        "never_overrides": [
            "margin",
            "broker_validation",
            "market_closed",
            "invalid_volume",
            "invalid_stops",
            "emergency_stop",
        ],
    }


def log_risk_lock_override_startup(settings: Any | None = None) -> None:
    """Startup banner when ALLOW_RISK_LOCK_OVERRIDE is loaded."""
    enabled_env = False
    try:
        if settings is None:
            from core.config.settings import get_settings

            settings = get_settings()
        enabled_env = bool(getattr(settings, "allow_risk_lock_override", False))
    except Exception:
        enabled_env = False
    # Effective gate is always off after production finalization.
    logger.warning(
        "ALLOW_RISK_LOCK_OVERRIDE = %s (effective=FALSE)",
        "TRUE" if enabled_env else "FALSE",
    )
    if enabled_env:
        logger.warning(
            "ALLOW_RISK_LOCK_OVERRIDE ignored — permanently disabled for production"
        )
