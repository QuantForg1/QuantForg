"""Deterministic portfolio allocation optimizer — recommendations only."""

from __future__ import annotations

import math
from typing import Any


def _vol(series: list[float]) -> float | None:
    if len(series) < 5:
        return None
    mean = sum(series) / len(series)
    var = sum((x - mean) ** 2 for x in series) / (len(series) - 1)
    return math.sqrt(var) if var > 0 else None


def optimize_allocations(
    *,
    symbols: list[str],
    current_weights: dict[str, float],
    pnl_series: dict[str, list[float]],
    max_risk_pct: float,
    max_allocation_pct: float,
    target_volatility: float | None,
    target_return: float | None,
) -> dict[str, Any]:
    """Inverse-volatility / equal-weight allocation with hard constraints.

    Never places trades. Returns explainable recommendation payload.
    """
    if not symbols:
        return {
            "status": "unavailable",
            "reason": "No symbols to allocate",
            "recommendations": [],
            "autonomous_trading": False,
        }

    vols: dict[str, float] = {}
    missing_vol: list[str] = []
    for s in symbols:
        v = _vol(pnl_series.get(s, []))
        if v is None or v <= 0:
            missing_vol.append(s)
        else:
            vols[s] = v

    method = "inverse_volatility"
    raw: dict[str, float] = {}
    if len(vols) == len(symbols):
        inv = {s: 1.0 / vols[s] for s in symbols}
        total_inv = sum(inv.values())
        raw = {s: inv[s] / total_inv for s in symbols}
    else:
        method = "equal_weight_fallback"
        eq = 1.0 / len(symbols)
        raw = dict.fromkeys(symbols, eq)

    capped = {s: min(w, max_allocation_pct / 100.0) for s, w in raw.items()}
    tot = sum(capped.values())
    if tot <= 0:
        return {
            "status": "unavailable",
            "reason": "Allocation collapsed under constraints",
            "recommendations": [],
            "autonomous_trading": False,
        }
    weights = {s: capped[s] / tot for s in symbols}

    port_vol = None
    if method == "inverse_volatility" and vols:
        port_vol = sum(weights[s] * vols[s] for s in symbols)
        if target_volatility is not None and port_vol > target_volatility:
            scale = target_volatility / port_vol
            weights = {s: weights[s] * scale for s in symbols}

    invested = sum(weights.values())
    if invested * 100.0 > max_risk_pct:
        scale = (max_risk_pct / 100.0) / invested if invested > 0 else 0.0
        weights = {s: weights[s] * scale for s in symbols}

    mean_rets = {
        s: (sum(pnl_series[s]) / len(pnl_series[s]) if pnl_series.get(s) else None)
        for s in symbols
    }
    est_return = None
    if all(v is not None for v in mean_rets.values()):
        est_return = sum(
            weights[s] * float(mean_rets[s] or 0.0) for s in symbols
        )

    recommendations = []
    for s in symbols:
        cur = current_weights.get(s, 0.0)
        tgt = weights[s]
        recommendations.append(
            {
                "symbol": s,
                "current_weight_pct": round(cur * 100.0, 4),
                "target_weight_pct": round(tgt * 100.0, 4),
                "delta_weight_pct": round((tgt - cur) * 100.0, 4),
                "explanation": {
                    "reason": (
                        "Inverse-volatility weight under max allocation / risk caps"
                        if method == "inverse_volatility"
                        else "Equal weight fallback — insufficient PnL series for vol"
                    ),
                    "supporting_metrics": {
                        "symbol_vol": vols.get(s),
                        "mean_deal_pnl": mean_rets.get(s),
                        "method": method,
                    },
                    "risk_impact": {
                        "portfolio_vol_estimate": port_vol,
                        "max_allocation_pct": max_allocation_pct,
                        "max_risk_pct": max_risk_pct,
                        "target_volatility": target_volatility,
                        "target_return": target_return,
                        "estimated_mean_pnl": est_return,
                    },
                    "confidence": 0.7 if method == "inverse_volatility" else 0.35,
                    "data_source": (
                        "history_deals.symbol_pnl_series"
                        if method == "inverse_volatility"
                        else "open_positions.equal_weight"
                    ),
                },
            }
        )

    return {
        "status": "available",
        "method": method,
        "missing_volatility_symbols": missing_vol,
        "portfolio_vol_estimate": port_vol,
        "estimated_mean_pnl": est_return,
        "cash_weight_pct": round(max(0.0, 1.0 - sum(weights.values())) * 100.0, 4),
        "constraints": {
            "max_risk_pct": max_risk_pct,
            "max_allocation_pct": max_allocation_pct,
            "target_volatility": target_volatility,
            "target_return": target_return,
        },
        "recommendations": recommendations,
        "autonomous_trading": False,
        "note": "Recommendation only — never submits orders",
    }
