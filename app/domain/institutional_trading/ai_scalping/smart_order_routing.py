"""Smart Order Routing — expected slippage / fill probability / EQ score.

Annotates execution readiness. Never changes AI direction or decision.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

_LOCK = threading.RLock()
_LAST: dict[str, Any] | None = None


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def estimate_smart_routing(
    *,
    symbol: str,
    side: str | None = None,
    spread: Any = None,
    optimizer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute expected slippage, fill probability, execution quality score."""
    opt = optimizer if isinstance(optimizer, dict) else {}
    quality = int(opt.get("execution_quality_score") or 50)
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        eq = get_execution_quality_store().snapshot()
    except Exception:
        eq = {}

    hist_slip = _f(eq.get("avg_slippage"), None)
    fill_rate = _f(eq.get("fill_rate"), None)
    reject_rate = _f(eq.get("reject_rate"), None)
    spread_f = _f(spread, None)

    # Expected slippage: prefer history; else soft estimate from spread
    if hist_slip is not None:
        expected_slippage = abs(hist_slip)
    elif spread_f is not None:
        expected_slippage = abs(spread_f) * 0.35
    else:
        expected_slippage = None

    if fill_rate is not None:
        fill_probability = max(0.05, min(0.98, fill_rate / 100.0))
    else:
        fill_probability = max(0.05, min(0.95, quality / 100.0))

    # Execution quality score blends optimizer + fill/reject history
    hist_score = 55
    if fill_rate is not None:
        hist_score = int(
            max(10, min(95, fill_rate - 0.5 * float(reject_rate or 0)))
        )
    execution_quality_score = int(round(0.55 * quality + 0.45 * hist_score))

    poor = execution_quality_score < 55
    recommendation = "WAIT_BETTER_TICK" if poor else "SUBMIT"
    if opt.get("recommendation") == "PROCEED_DEGRADED":
        recommendation = "SUBMIT_DEGRADED"
        poor = False

    payload = {
        "as_of": _iso(),
        "symbol": str(symbol or "").upper(),
        "side": str(side or "").upper() or None,
        "expected_slippage": (
            round(expected_slippage, 6) if expected_slippage is not None else None
        ),
        "fill_probability": round(fill_probability, 4),
        "execution_quality_score": execution_quality_score,
        "poor_execution_quality": poor,
        "recommendation": recommendation,
        "inputs": {
            "optimizer_score": quality,
            "avg_slippage": hist_slip,
            "fill_rate": fill_rate,
            "reject_rate": reject_rate,
            "spread": spread_f,
            "samples": eq.get("samples"),
        },
        "direction_unchanged": True,
        "ai_decision_unchanged": True,
        "forced_trades": False,
        "fabricated": False,
        "source": "existing_eq_and_optimizer",
    }
    global _LAST
    with _LOCK:
        _LAST = dict(payload)
    return payload


def get_last_smart_routing() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_LAST) if _LAST else None
