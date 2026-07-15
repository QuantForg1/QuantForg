"""Research Lab — parameter sandbox (never mutates production defaults)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PRODUCTION_DEFAULTS: dict[str, Any] = {
    "atr_period": 14,
    "ema_fast": 20,
    "ema_slow": 50,
    "ema_trend": 200,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "volume_min": 0,
    "session": "London",
    "max_risk_pct": 0.5,
    "stop_loss_distance": "0.0020",
    "take_profit_distance": "0.0040",
}


def sandbox_parameters(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge overrides onto a copy of production defaults — production untouched."""
    base = deepcopy(PRODUCTION_DEFAULTS)
    applied: dict[str, Any] = {}
    rejected: list[str] = []
    for k, v in (overrides or {}).items():
        if k not in base:
            rejected.append(f"Unknown parameter '{k}' ignored")
            continue
        applied[k] = v
        base[k] = v
    return {
        "status": "available",
        "parameters": base,
        "overrides_applied": applied,
        "rejected": rejected,
        "production_defaults_unchanged": True,
        "sandbox": True,
        "advisory_only": True,
        "never_modifies_production_defaults": True,
    }


def to_backtest_assumptions(sandbox: dict[str, Any]) -> dict[str, str]:
    params = dict(sandbox.get("parameters") or {})
    return {
        "stop_loss_distance": str(params.get("stop_loss_distance", "0.0020")),
        "take_profit_distance": str(params.get("take_profit_distance", "0.0040")),
        "lot_size": "0.10",
        "preferred_session": str(params.get("session", "London")),
    }
