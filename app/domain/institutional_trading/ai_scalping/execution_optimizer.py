"""Execution Optimizer — choose optimal submit moment without changing AI/Risk.

Uses existing spread / latency / slippage / EQ history only.
Never changes direction. Never forces trades. Soft defer only within limits.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

_LOCK = threading.RLock()
_DEFER_COUNTS: dict[str, dict[str, Any]] = {}
_LAST_OPTIMIZER: dict[str, Any] | None = None

# Fallback bounds when config cannot be loaded. Prefer AiScalpingConfig.
_FALLBACK_MAX_DEFERS = 2
_FALLBACK_MAX_DEFER_MS = 2500
_FALLBACK_PROCEED_QUALITY = 45
_FALLBACK_DEFER_BELOW_QUALITY = 40

HARD_BLOCK_REASONS = frozenset(
    {
        "STALE_MARKET_DATA",
        "MISSING_QUOTE",
        "MARKET_CLOSED",
        "UNACCEPTABLE_SPREAD",
        "INVALID_PRICE",
        "INSUFFICIENT_MARGIN",
        "MIN_LOT_CONSTRAINT",
        "PORTFOLIO_RISK_LIMIT",
        "SAFETY_BLOCK",
        "RISK_BLOCK",
        "RECONCILIATION_REQUIRED",
        "KILL_SWITCH",
        "BURST_LATCH",
        "EXECUTION_AUTHORITY_DISABLED",
        "NO_ELIGIBLE_SETUP",
    }
)


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
    # Gold scalp ATR% routinely 0.08–0.35 on Sydney/Tokyo. Treating <0.15 as
    # "compression" scored 35 and held LIVE submits at quality 54 (DEFER forever
    # because each cycle uses a new decision hash). Align with vol hard_min 0.08.
    if atr_pct < 0.08:
        return {"atr_pct": round(atr_pct, 6), "band": "compression", "score": 35}
    if atr_pct < 0.12:
        return {"atr_pct": round(atr_pct, 6), "band": "thin", "score": 60}
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


def _optimizer_bounds() -> tuple[int, int, int, int]:
    """(max_attempts, max_duration_ms, proceed_quality, defer_below_quality)."""
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        cfg = DEFAULT_AI_SCALPING_CONFIG
        return (
            int(cfg.optimizer_max_defer_attempts),
            int(cfg.optimizer_max_defer_duration_ms),
            int(cfg.optimizer_proceed_quality),
            int(cfg.optimizer_defer_below_quality),
        )
    except Exception:
        return (
            _FALLBACK_MAX_DEFERS,
            _FALLBACK_MAX_DEFER_MS,
            _FALLBACK_PROCEED_QUALITY,
            _FALLBACK_DEFER_BELOW_QUALITY,
        )


def _defer_state(decision_key: str) -> dict[str, Any]:
    """Read defer bookkeeping. Never reset the window — expiry means EXECUTE."""
    with _LOCK:
        row = _DEFER_COUNTS.get(decision_key)
        if not row:
            return {"count": 0, "first_at": None, "elapsed_ms": 0}
        first = row.get("first_at")
        elapsed_ms = 0
        try:
            when = datetime.fromisoformat(str(first).replace("Z", "+00:00"))
            elapsed_ms = int(max(0.0, (_now() - when).total_seconds() * 1000.0))
        except Exception:
            elapsed_ms = 0
        return {
            "count": int(row.get("count") or 0),
            "first_at": first,
            "elapsed_ms": elapsed_ms,
        }


def _bump_defer(decision_key: str) -> int:
    with _LOCK:
        row = _DEFER_COUNTS.get(decision_key)
        if not row:
            row = {"count": 0, "first_at": _iso()}
        elif not row.get("first_at"):
            row["first_at"] = _iso()
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
    hard_block_reason: str | None = None,
    hard_gates_pass: bool = True,
) -> dict[str, Any]:
    """Score current micro-structure for OMS submit timing.

    Soft optimizer only. Hard Safety/Risk/spread/stale gates belong upstream.
    Returns final_state EXECUTE_NOW | WAIT_BOUNDED | BLOCK.
    Never alters AI direction. Never forces a trade. Never waits forever.
    """
    max_attempts, max_defer_ms, proceed_q, defer_below_q = _optimizer_bounds()
    sym = str(symbol or getattr(decision, "symbol", "") or "").upper()
    action = str(
        getattr(getattr(decision, "action", None), "value", None)
        or getattr(decision, "action", None)
        or ""
    ).upper()
    key = (
        decision_key
        or f"{sym}:{action}"
        or str(getattr(decision, "input_hash", None) or sym or "na")
    )
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

    block_code = str(hard_block_reason or "").strip().upper() or None
    if block_code in HARD_BLOCK_REASONS or hard_gates_pass is False:
        recommendation = "SKIP"
        final_state = "BLOCK"
        reason = block_code or "HARD_GATE_FAILED"
        remaining_wait_ms = 0
        remaining_attempts = max(0, max_attempts - int(defer["count"]))
    elif action not in {"BUY", "SELL"}:
        recommendation = "SKIP"
        final_state = "BLOCK"
        reason = "no_buy_sell_action"
        remaining_wait_ms = 0
        remaining_attempts = max(0, max_attempts - int(defer["count"]))
    else:
        spread_worsening = str(spread.get("trend") or "") == "worsening"
        momentum_spike = str(mom.get("momentum") or "") == "spike"
        current_tick_acceptable = quality >= proceed_q
        better_tick_required = quality < defer_below_q and (
            spread_worsening or momentum_spike
        )
        elapsed_ms = int(defer["elapsed_ms"] or 0)
        count = int(defer["count"] or 0)
        remaining_wait_ms = max(0, max_defer_ms - elapsed_ms)
        remaining_attempts = max(0, max_attempts - count)
        bound_exhausted = remaining_wait_ms <= 0 or remaining_attempts <= 0

        if (not better_tick_required) or current_tick_acceptable:
            recommendation = "PROCEED"
            final_state = "EXECUTE_NOW"
            reason = "all_hard_gates_pass_current_tick_acceptable"
            remaining_wait_ms = 0
        elif bound_exhausted:
            recommendation = "PROCEED_DEGRADED"
            final_state = "EXECUTE_NOW"
            reason = (
                "max_defer_duration_reached_submit"
                if remaining_wait_ms <= 0
                else "max_defers_reached_submit_anyway"
            )
            remaining_wait_ms = 0
        else:
            recommendation = "DEFER_TICK"
            final_state = "WAIT_BOUNDED"
            reason = (
                "spread_improvement_expected"
                if spread_worsening
                else "wait_for_better_tick_within_limits"
            )
            _bump_defer(key)
            defer = _defer_state(key)
            remaining_wait_ms = max(0, max_defer_ms - int(defer["elapsed_ms"] or 0))
            remaining_attempts = max(0, max_attempts - int(defer["count"] or 0))

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
        "final_state": final_state,
        "reason": reason,
        "defer_count": _defer_state(key)["count"],
        "defer_started_at": _defer_state(key)["first_at"],
        "max_defers": max_attempts,
        "max_defer_attempts": max_attempts,
        "max_defer_duration_ms": max_defer_ms,
        "max_defer_window_seconds": round(max_defer_ms / 1000.0, 3),
        "remaining_wait_ms": int(remaining_wait_ms),
        "remaining_attempts": int(remaining_attempts),
        "decision_key": key,
        "current_tick_acceptable": quality >= proceed_q,
        "better_tick_required": reason
        in {
            "spread_improvement_expected",
            "wait_for_better_tick_within_limits",
        },
        "forced_trades": False,
        "direction_unchanged": True,
        "fabricated": False,
        "source": "existing_production_metrics_only",
    }
    global _LAST_OPTIMIZER
    with _LOCK:
        _LAST_OPTIMIZER = dict(payload)
    return payload


def should_defer_submit(payload: dict[str, Any] | None) -> bool:
    """True only for an in-bound soft wait. EXECUTE_NOW / BLOCK never defer."""
    if not isinstance(payload, dict):
        return False
    return str(payload.get("final_state") or "") == "WAIT_BOUNDED"


def get_last_execution_optimizer() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_LAST_OPTIMIZER) if _LAST_OPTIMIZER else None


def clear_optimizer_defers(decision_key: str | None = None) -> None:
    with _LOCK:
        if decision_key:
            _DEFER_COUNTS.pop(decision_key, None)
        else:
            _DEFER_COUNTS.clear()
