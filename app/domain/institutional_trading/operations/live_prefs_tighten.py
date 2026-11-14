"""Tighten LIVE RiskEngineConfig from customer Risk Center prefs.

Customer knobs may only **reduce** owner/ITE ceilings — never loosen.
Missing or invalid prefs leave the incoming config unchanged (fail to owner).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.domain.entities.risk_engine import RiskEngineConfig


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def _int_pos(value: object) -> int | None:
    try:
        n = int(str(value))
    except (TypeError, ValueError):
        return None
    return n if n >= 1 else None


def tighten_risk_config_from_effective(
    config: RiskEngineConfig,
    effective: dict[str, Any] | None,
) -> RiskEngineConfig:
    """Apply an already-resolved effective profile as tighten-only clamps."""
    if not effective:
        return config
    planned = _dec(effective.get("planned_risk_pct"))
    max_lot = _dec(effective.get("max_lot"))
    daily = _dec(effective.get("daily_loss_pct"))
    max_open = _int_pos(effective.get("max_concurrent_positions"))
    # Phase 3: customer aggregate open-risk ceiling — tighten exposure caps only.
    aggregate_open = _dec(effective.get("aggregate_open_risk_pct"))

    updates: dict[str, Any] = {}
    if planned is not None:
        updates["max_risk_per_trade_pct"] = min(config.max_risk_per_trade_pct, planned)
    if max_lot is not None:
        updates["max_lot"] = min(config.max_lot, max_lot)
        updates["fixed_lot"] = min(config.fixed_lot, max_lot)
    if daily is not None and config.max_daily_loss_pct > 0:
        updates["max_daily_loss_pct"] = min(config.max_daily_loss_pct, daily)
    if max_open is not None:
        updates["max_open_positions"] = min(config.max_open_positions, max_open)
    if aggregate_open is not None:
        updates["max_total_exposure_pct"] = min(
            config.max_total_exposure_pct, aggregate_open
        )
        updates["max_correlated_exposure_pct"] = min(
            config.max_correlated_exposure_pct, aggregate_open
        )
    if not updates:
        return config
    return replace(config, **updates)


def tighten_live_risk_config_for_user(
    config: RiskEngineConfig,
    user_id: UUID | None,
) -> RiskEngineConfig:
    """Load user prefs (best-effort) and tighten LIVE risk config."""
    if user_id is None:
        return config
    try:
        from app.application.services.user_risk_preferences_service import (
            get_user_risk_preferences,
        )

        payload = get_user_risk_preferences(user_id)
    except Exception:
        # Prefs optional; keep owner ceilings on any load failure.
        return config
    effective = payload.get("effective") if isinstance(payload, dict) else None
    if not isinstance(effective, dict):
        return config
    if effective.get("ok") is False:
        return config
    return tighten_risk_config_from_effective(config, effective)
