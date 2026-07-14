"""Quant Studio — AI optimizer suggestions (never auto-applies)."""

from __future__ import annotations

from typing import Any


def suggest_optimizations(
    *,
    metrics: dict[str, Any],
    assumptions: dict[str, Any] | None = None,
    session: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """Suggest SL/TP/RR/risk/session — user must apply manually."""
    assumptions = dict(assumptions or {})
    suggestions: list[dict[str, str]] = []

    def _f(key: str, default: float | None = None) -> float | None:
        raw = metrics.get(key)
        if raw is None:
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    try:
        sl = float(assumptions.get("stop_loss_distance") or 0.002)
        tp = float(assumptions.get("take_profit_distance") or 0.004)
    except (TypeError, ValueError):
        sl, tp = 0.002, 0.004

    wr = _f("win_rate")
    dd = _f("max_drawdown_pct")
    pf = _f("profit_factor")
    avg_r = _f("average_r")

    if avg_r is not None and avg_r < 1.0:
        suggestions.append(
            {
                "field": "tp_distance",
                "current": str(tp),
                "suggested": f"{sl * 2.0:.5f}",
                "reason": "Average R below 1 — widen TP toward ~2R",
            }
        )
        suggestions.append(
            {
                "field": "rr",
                "current": f"{(tp / sl) if sl else 0:.2f}",
                "suggested": "2.00",
                "reason": "Target minimum 2:1 reward-to-risk",
            }
        )

    if wr is not None and wr < 45 and sl > 0:
        suggestions.append(
            {
                "field": "sl_distance",
                "current": str(sl),
                "suggested": f"{sl * 1.25:.5f}",
                "reason": "Low win rate — slightly wider SL may reduce noise stops",
            }
        )

    if dd is not None and dd >= 15:
        lot = assumptions.get("lot_size") or "0.10"
        try:
            new_lot = max(0.01, float(lot) * 0.7)
        except (TypeError, ValueError):
            new_lot = 0.07
        suggestions.append(
            {
                "field": "risk",
                "current": str(lot),
                "suggested": f"{new_lot:.2f}",
                "reason": f"Drawdown {dd:.1f}% — reduce position size for risk control",
            }
        )

    if pf is not None and pf < 1.2:
        suggestions.append(
            {
                "field": "session",
                "current": session or "unspecified",
                "suggested": "London|NewYork",
                "reason": "Weak PF — prefer higher-liquidity sessions",
            }
        )

    if timeframe:
        suggestions.append(
            {
                "field": "timeframe",
                "current": timeframe,
                "suggested": timeframe,
                "reason": "Keep timeframe unless walk-forward shows regime mismatch",
            }
        )

    if symbol:
        suggestions.append(
            {
                "field": "symbol",
                "current": symbol,
                "suggested": symbol,
                "reason": "Symbol retained — optimizer never auto-switches instruments",
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "field": "none",
                "current": "—",
                "suggested": "—",
                "reason": "Metrics do not justify parameter changes",
            }
        )

    return {
        "status": "available",
        "suggestions": suggestions,
        "applied": False,
        "why": {
            "summary": "Advisory optimizer suggestions — user settings unchanged",
            "supporting_factors": [s["reason"] for s in suggestions[:5]],
        },
        "autonomous_trading": False,
        "advisory_only": True,
        "never_modifies_user_settings": True,
        "never_submits_orders": True,
    }
