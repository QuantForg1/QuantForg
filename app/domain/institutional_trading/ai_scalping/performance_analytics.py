"""Performance Analytics — REAL completed trades only (learning + post-trade)."""

from __future__ import annotations

import math
from typing import Any


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def build_performance_analytics() -> dict[str, Any]:
    """Aggregate win rate, RR, hold, PF, sharpe, expectancy, Q/C, best/worst."""
    learning_rows: list[Any] = []
    learning_summary: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        store = get_scalping_learning_store()
        learning_summary = store.summary()
        with store._lock:
            learning_rows = list(store._records)
    except Exception:
        learning_summary = {"trades": 0, "wins": 0, "losses": 0, "win_rate": None}

    post_summary: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.post_trade_analytics import (
            get_post_trade_journal,
        )

        post_summary = get_post_trade_journal().performance_snapshot()
    except Exception:
        post_summary = {}

    trades = len(learning_rows)
    wins = sum(1 for r in learning_rows if getattr(r, "win", False))
    losses = trades - wins
    win_rate = (wins / trades) if trades else None

    pnls = [_safe_float(getattr(r, "pnl", None)) for r in learning_rows]
    pnls_f = [p for p in pnls if p is not None]
    gross_profit = sum(p for p in pnls_f if p > 0)
    gross_loss = abs(sum(p for p in pnls_f if p < 0))
    profit_factor: float | None = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    # else undefined / infinite — leave null, never invent

    avg_rr = None
    rr_vals = [
        _safe_float(getattr(r, "r_multiple", None))
        for r in learning_rows
        if getattr(r, "r_multiple", None) is not None
    ]
    rr_vals = [v for v in rr_vals if v is not None]
    if rr_vals:
        avg_rr = sum(rr_vals) / len(rr_vals)

    holds = [
        getattr(r, "holding_time_minutes", None)
        for r in learning_rows
        if getattr(r, "holding_time_minutes", None) is not None
    ]
    avg_hold = (sum(float(h) for h in holds) / len(holds)) if holds else None

    qualities = [int(getattr(r, "quality", 0) or 0) for r in learning_rows]
    confidences = [int(getattr(r, "confidence", 0) or 0) for r in learning_rows]
    avg_quality = (sum(qualities) / len(qualities)) if qualities else None
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else None

    expectancy = None
    if trades and pnls_f:
        expectancy = sum(pnls_f) / trades

    sharpe = None
    if len(pnls_f) >= 2:
        mean = sum(pnls_f) / len(pnls_f)
        var = sum((x - mean) ** 2 for x in pnls_f) / (len(pnls_f) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            sharpe = mean / std

    # Best / worst sessions & symbols by win rate (min 2 samples)
    def _best_worst(bucket: dict[str, dict[str, int]]) -> tuple[str | None, str | None]:
        scored: list[tuple[str, float, int]] = []
        for key, stats in bucket.items():
            n = int(stats.get("trades") or 0)
            if n < 2:
                continue
            w = int(stats.get("wins") or 0)
            scored.append((key, w / n, n))
        if not scored:
            return None, None
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return scored[0][0], scored[-1][0]

    by_session = learning_summary.get("by_session") or {}
    by_symbol = learning_summary.get("by_symbol") or {}
    sess_map = by_session if isinstance(by_session, dict) else {}
    sym_map = by_symbol if isinstance(by_symbol, dict) else {}
    best_session, worst_session = _best_worst(sess_map)
    best_symbol, worst_symbol = _best_worst(sym_map)

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "average_rr": round(avg_rr, 4) if avg_rr is not None else None,
        "average_hold_time_minutes": (
            round(avg_hold, 2) if avg_hold is not None else None
        ),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "average_quality": round(avg_quality, 2) if avg_quality is not None else None,
        "average_confidence": (
            round(avg_confidence, 2) if avg_confidence is not None else None
        ),
        "best_session": best_session,
        "worst_session": worst_session,
        "best_symbol": best_symbol,
        "worst_symbol": worst_symbol,
        "post_trade_summary": post_summary,
        "source": "real_completed_trades_only",
        "fabricated": False,
        "observe_only": True,
    }
