"""Execution Optimizer — choose optimal submit moment without changing AI/Risk.

Uses existing spread / latency / slippage / EQ history only.
Never changes direction. Never forces trades. Soft defer only within limits.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

_LOCK = threading.RLock()
_DEFER_COUNTS: dict[str, dict[str, Any]] = {}
_LAST_OPTIMIZER: dict[str, Any] | None = None

# Soft limits — never hold forever
MAX_DEFERS_PER_DECISION = 3
MAX_DEFER_WINDOW_SECONDS = 45
MIN_QUALITY_TO_PROCEED = 45
DEFER_BELOW_QUALITY = 55


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat().replace("+00:00", "Z")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _spread_trend(symbol: str) -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
            spread_history_values,
        )

        hist = [float(x) for x in spread_history_values(symbol)]
        if len(hist) < 2:
            return {"samples": len(hist), "trend": "unknown", "score": 50}
        recent = hist[-8:]
        half = max(1, len(recent) // 2)
        first = sum(recent[:half]) / half
        last = sum(recent[half:]) / max(1, len(recent) - half)
        if last < first * 0.95:
            return {"samples": len(hist), "trend": "improving", "score": 80}
        if last > first * 1.05:
            return {"samples": len(hist), "trend": "worsening", "score": 30}
        return {"samples": len(hist), "trend": "stable", "score": 60}
    except Exception:
        return {"samples": 0, "trend": "unknown", "score": 50}


def _tick_momentum(snapshot: Any) -> dict[str, Any]:
    """Micro momentum from entry closes when present — never invents ticks."""
    closes = tuple(getattr(snapshot, "entry_closes", ()) or ())
    if len(closes) < 3:
        return {"samples": len(closes), "momentum": "unknown", "score": 50}
    try:
        a = float(closes[-3])
        b = float(closes[-1])
        if a <= 0:
            return {"samples": len(closes), "momentum": "unknown", "score": 50}
        chg = (b - a) / a
        if abs(chg) < 1e-6:
            return {"samples": len(closes), "momentum": "flat", "score": 55}
        # Direction-agnostic: calm micro move scores higher than spike
        if abs(chg) < 0.0004:
            return {"samples": len(closes), "momentum": "calm", "score": 75}
        if abs(chg) < 0.001:
            return {"samples": len(closes), "momentum": "moderate", "score": 60}
        return {"samples": len(closes), "momentum": "spike", "score": 35}
    except Exception:
        return {"samples": len(closes), "momentum": "unknown", "score": 50}


def _micro_volatility(snapshot: Any, account: Any) -> dict[str, Any]:
    atr = _f(getattr(account, "atr", None), 0.0)
    mid = _f(getattr(account, "mid_price", None), 0.0)
    if atr <= 0 or mid <= 0:
        return {"atr_pct": None, "band": "unknown", "score": 50}
    atr_pct = (atr / mid) * 100.0
    if atr_pct < 0.15:
        return {"atr_pct": round(atr_pct, 6), "band": "compression", "score": 35}
    if atr_pct > 2.5:
        return {"atr_pct": round(atr_pct, 6), "band": "expansion", "score": 40}
    return {"atr_pct": round(atr_pct, 6), "band": "normal", "score": 75}


def _latency_score() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        snap = get_execution_quality_store().snapshot()
        avg = snap.get("avg_latency_ms")
        if avg is None:
            return {"avg_latency_ms": None, "score": 55}
        avg_f = float(avg)
        if avg_f < 250:
            score = 85
        elif avg_f < 800:
            score = 65
        elif avg_f < 2000:
            score = 40
        else:
            score = 20
        return {"avg_latency_ms": avg_f, "score": score, "samples": snap.get("samples")}
    except Exception:
        return {"avg_latency_ms": None, "score": 55}


def _broker_response_score() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        snap = get_execution_quality_store().snapshot()
        fill = snap.get("fill_rate")
        reject = snap.get("reject_rate")
        if fill is None:
            return {"fill_rate": None, "reject_rate": None, "score": 55}
        score = max(10, min(95, float(fill) - 0.4 * float(reject or 0)))
        return {
            "fill_rate": fill,
            "reject_rate": reject,
            "requote_rate": snap.get("requote_rate"),
            "score": int(round(score)),
            "samples": snap.get("samples"),
        }
    except Exception:
        return {"fill_rate": None, "reject_rate": None, "score": 55}


def _slippage_history_score() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        snap = get_execution_quality_store().snapshot()
        avg = snap.get("avg_slippage")
        if avg is None:
            return {"avg_slippage": None, "score": 55}
        avg_f = abs(float(avg))
        if avg_f < 0.05:
            score = 85
        elif avg_f < 0.15:
            score = 65
        elif avg_f < 0.35:
            score = 40
        else:
            score = 20
        return {"avg_slippage": avg_f, "score": score, "samples": snap.get("samples")}
    except Exception:
        return {"avg_slippage": None, "score": 55}


def _defer_state(decision_key: str) -> dict[str, Any]:
    with _LOCK:
        row = _DEFER_COUNTS.get(decision_key)
        if not row:
            return {"count": 0, "first_at": None}
        first = row.get("first_at")
        try:
            when = datetime.fromisoformat(str(first).replace("Z", "+00:00"))
            if _now() - when > timedelta(seconds=MAX_DEFER_WINDOW_SECONDS):
                _DEFER_COUNTS.pop(decision_key, None)
                return {"count": 0, "first_at": None}
        except Exception:
            pass
        return {"count": int(row.get("count") or 0), "first_at": first}


def _bump_defer(decision_key: str) -> int:
    with _LOCK:
        row = _DEFER_COUNTS.get(decision_key) or {"count": 0, "first_at": _iso()}
        row["count"] = int(row.get("count") or 0) + 1
        _DEFER_COUNTS[decision_key] = row
        return int(row["count"])


def evaluate_execution_moment(
    *,
    symbol: str,
    decision: Any | None = None,
    snapshot: Any | None = None,
    account: Any | None = None,
    decision_key: str | None = None,
) -> dict[str, Any]:
    """Score current micro-structure for OMS submit timing.

    Returns recommendation PROCEED | DEFER_TICK | PROCEED_DEGRADED.
    Never alters AI direction. Never forces a trade.
    """
    sym = str(symbol or getattr(decision, "symbol", "") or "").upper()
    key = decision_key or str(getattr(decision, "input_hash", None) or sym or "na")
    spread = _spread_trend(sym)
    mom = _tick_momentum(snapshot)
    vol = _micro_volatility(snapshot, account)
    lat = _latency_score()
    broker = _broker_response_score()
    slip = _slippage_history_score()

    components = {
        "spread_trend": int(spread["score"]),
        "tick_momentum": int(mom["score"]),
        "micro_volatility": int(vol["score"]),
        "execution_latency": int(lat["score"]),
        "broker_response_history": int(broker["score"]),
        "slippage_history": int(slip["score"]),
    }
    # Equal-ish weights; quality dominant factors listed first
    weights = {
        "spread_trend": 20,
        "tick_momentum": 15,
        "micro_volatility": 15,
        "execution_latency": 20,
        "broker_response_history": 15,
        "slippage_history": 15,
    }
    total_w = sum(weights.values()) or 1
    quality = int(
        round(sum(components[k] * weights[k] for k in weights) / total_w)
    )
    defer = _defer_state(key)
    action = str(getattr(getattr(decision, "action", None), "value", None) or "")
    if action.upper() not in {"BUY", "SELL"}:
        recommendation = "SKIP"
        reason = "no_buy_sell_action"
    elif quality >= DEFER_BELOW_QUALITY:
        recommendation = "PROCEED"
        reason = "execution_moment_acceptable"
    elif defer["count"] >= MAX_DEFERS_PER_DECISION:
        recommendation = "PROCEED_DEGRADED"
        reason = "max_defers_reached_submit_anyway"
    elif defer["first_at"] is not None:
        recommendation = "DEFER_TICK"
        reason = "await_better_tick_within_limits"
        _bump_defer(key)
    else:
        recommendation = "DEFER_TICK"
        reason = "await_better_tick_within_limits"
        _bump_defer(key)

    # Absolute floor: never block forever — if quality catastrophic but
    # max defers hit, PROCEED_DEGRADED already set. If quality above min
    # after defer bump still DEFER — ok.
    if recommendation == "DEFER_TICK" and quality < MIN_QUALITY_TO_PROCEED:
        # Still allow defer only within window; otherwise proceed degraded
        if defer["count"] + 1 >= MAX_DEFERS_PER_DECISION:
            recommendation = "PROCEED_DEGRADED"
            reason = "poor_quality_but_defer_limit"

    payload = {
        "as_of": _iso(),
        "symbol": sym,
        "execution_quality_score": quality,
        "components": components,
        "details": {
            "spread_trend": spread,
            "tick_momentum": mom,
            "micro_volatility": vol,
            "execution_latency": lat,
            "broker_response_history": broker,
            "slippage_history": slip,
        },
        "recommendation": recommendation,
        "reason": reason,
        "defer_count": _defer_state(key)["count"],
        "max_defers": MAX_DEFERS_PER_DECISION,
        "max_defer_window_seconds": MAX_DEFER_WINDOW_SECONDS,
        "decision_key": key,
        "forced_trades": False,
        "direction_unchanged": True,
        "fabricated": False,
        "source": "existing_production_metrics_only",
    }
    global _LAST_OPTIMIZER
    with _LOCK:
        _LAST_OPTIMIZER = dict(payload)
    return payload


def get_last_execution_optimizer() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_LAST_OPTIMIZER) if _LAST_OPTIMIZER else None


def clear_optimizer_defers(decision_key: str | None = None) -> None:
    with _LOCK:
        if decision_key:
            _DEFER_COUNTS.pop(decision_key, None)
        else:
            _DEFER_COUNTS.clear()
