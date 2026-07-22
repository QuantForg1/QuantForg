"""Offline counterfactual analysis for NO_TRADE decisions — research only."""

from __future__ import annotations

from typing import Any


def _f(raw: Any, default: float | None = None) -> float | None:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def evaluate_counterfactual(
    *,
    direction: str | None,
    entry: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    bars_after: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """If the NO_TRADE had been taken, would TP or SL have occurred first?

    Offline / research only. Never feeds production KPIs. Never invents bars.
    """
    base: dict[str, Any] = {
        "research_only": True,
        "feeds_production_kpis": False,
        "status": "unavailable",
        "result": None,
        "bars_evaluated": 0,
        "note": "Counterfactual is research-only — never mixes into live KPIs",
    }
    side = (direction or "").strip().upper()
    if side not in {"BUY", "SELL", "LONG", "SHORT"}:
        return {
            **base,
            "reason": "Missing or invalid direction for counterfactual",
        }
    if entry is None or stop_loss is None or take_profit is None:
        return {
            **base,
            "reason": "Missing entry / SL / TP — never invents levels",
        }
    if not bars_after:
        return {
            **base,
            "reason": "No subsequent bars supplied — never invents OHLC",
        }

    is_long = side in {"BUY", "LONG"}
    n = 0
    for bar in bars_after:
        if not isinstance(bar, dict):
            continue
        high = _f(bar.get("high"))
        low = _f(bar.get("low"))
        if high is None or low is None:
            continue
        n += 1
        if is_long:
            hit_sl = low <= stop_loss
            hit_tp = high >= take_profit
        else:
            hit_sl = high >= stop_loss
            hit_tp = low <= take_profit
        if hit_sl and hit_tp:
            # Same bar: conservative — mark ambiguous, do not guess
            return {
                **base,
                "status": "available",
                "result": "ambiguous_same_bar",
                "bars_evaluated": n,
                "note": (
                    "Both SL and TP touched in one bar — marked ambiguous; "
                    "research only; never fabricates which came first"
                ),
            }
        if hit_sl:
            return {
                **base,
                "status": "available",
                "result": "sl_first",
                "bars_evaluated": n,
            }
        if hit_tp:
            return {
                **base,
                "status": "available",
                "result": "tp_first",
                "bars_evaluated": n,
            }

    return {
        **base,
        "status": "available",
        "result": "neither",
        "bars_evaluated": n,
        "reason": "Neither TP nor SL reached in supplied bars",
    }


def analyze_no_trade_counterfactuals(
    opportunities: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Batch counterfactuals for NO_TRADE rows only."""
    rows: list[dict[str, Any]] = []
    for raw in opportunities or []:
        if not isinstance(raw, dict):
            continue
        decision = str(raw.get("decision") or raw.get("action") or "").upper()
        if decision != "NO_TRADE":
            continue
        cf = evaluate_counterfactual(
            direction=raw.get("direction") or raw.get("side"),
            entry=_f(raw.get("entry") or raw.get("entry_price")),
            stop_loss=_f(raw.get("stop_loss") or raw.get("sl")),
            take_profit=_f(raw.get("take_profit") or raw.get("tp")),
            bars_after=raw.get("bars_after") or raw.get("subsequent_bars"),
        )
        rows.append(
            {
                "timestamp": raw.get("timestamp"),
                "no_trade_reason": raw.get("no_trade_reason") or raw.get("reason"),
                "counterfactual": cf,
                "research_only": True,
            }
        )

    histogram: dict[str, int] = {}
    for row in rows:
        result = (row.get("counterfactual") or {}).get("result") or "unavailable"
        histogram[str(result)] = histogram.get(str(result), 0) + 1

    return {
        "status": "available" if rows else "unavailable",
        "research_only": True,
        "feeds_production_kpis": False,
        "no_trade_count": len(rows),
        "results": rows,
        "result_histogram": histogram,
        "note": "Counterfactual outcomes are research-only and never enter live KPIs",
    }
