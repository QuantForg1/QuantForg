"""Institutional Performance KPIs (AI v8) — REAL completed trades only."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _learning_rows() -> list[Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        store = get_scalping_learning_store()
        with store._lock:
            return list(store._records)
    except Exception:
        return []


def build_institutional_performance_kpis() -> dict[str, Any]:
    """Sharpe/Sortino/Calmar/Ulcer/MAE/MFE/EQI/Institutional Score from real trades."""
    rows = _learning_rows()
    pnls = [_f(getattr(r, "pnl", None)) for r in rows]
    pnls_f = [p for p in pnls if p is not None]
    n = len(pnls_f)
    wins = sum(1 for r in rows if getattr(r, "win", False))
    losses = len(rows) - wins

    expectancy = (sum(pnls_f) / n) if n else None
    gross_profit = sum(p for p in pnls_f if p > 0)
    gross_loss = abs(sum(p for p in pnls_f if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    sharpe = None
    sortino = None
    if n >= 2:
        mean = sum(pnls_f) / n
        var = sum((x - mean) ** 2 for x in pnls_f) / (n - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            sharpe = mean / std
        downside = [x for x in pnls_f if x < 0]
        if len(downside) >= 1:
            dvar = sum(x * x for x in downside) / len(downside)
            dstd = math.sqrt(dvar) if dvar > 0 else 0.0
            if dstd > 0:
                sortino = mean / dstd

    # Equity curve for Calmar / Ulcer / Recovery
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    dd_sq_sum = 0.0
    for p in pnls_f:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        dd_sq_sum += dd * dd
    ulcer = math.sqrt(dd_sq_sum / n) if n else None
    total_return = equity
    calmar = (total_return / max_dd) if max_dd > 0 else None
    recovery_factor = (total_return / max_dd) if max_dd > 0 else None

    mae_vals = [_f(getattr(r, "mae_r", None)) for r in rows]
    mae_vals = [v for v in mae_vals if v is not None]
    mfe_vals = [_f(getattr(r, "mfe_r", None)) for r in rows]
    mfe_vals = [v for v in mfe_vals if v is not None]
    avg_mae = sum(mae_vals) / len(mae_vals) if mae_vals else None
    avg_mfe = sum(mfe_vals) / len(mfe_vals) if mfe_vals else None

    # Execution Quality Index from EQ store when present
    eqi = None
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        eq = get_execution_quality_store().snapshot()
        fill = eq.get("fill_rate")
        reject = eq.get("reject_rate")
        if fill is not None:
            eqi = round(float(fill) - 0.5 * float(reject or 0), 2)
    except Exception:
        eqi = None

    # Institutional Score 0-100 from available KPIs (null-safe, never invent)
    components: list[float] = []
    if expectancy is not None:
        components.append(max(0.0, min(100.0, 50 + expectancy * 10)))
    if sharpe is not None:
        components.append(max(0.0, min(100.0, 50 + sharpe * 20)))
    if profit_factor is not None:
        components.append(max(0.0, min(100.0, min(profit_factor, 3.0) / 3.0 * 100)))
    if eqi is not None:
        components.append(max(0.0, min(100.0, eqi)))
    institutional_score = (
        round(sum(components) / len(components), 2) if components else None
    )

    return {
        "as_of": _iso(),
        "trades": len(rows),
        "wins": wins,
        "losses": losses,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "sortino": round(sortino, 4) if sortino is not None else None,
        "calmar": round(calmar, 4) if calmar is not None else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "recovery_factor": (
            round(recovery_factor, 4) if recovery_factor is not None else None
        ),
        "ulcer_index": round(ulcer, 4) if ulcer is not None else None,
        "average_mae": round(avg_mae, 4) if avg_mae is not None else None,
        "average_mfe": round(avg_mfe, 4) if avg_mfe is not None else None,
        "execution_quality_index": eqi,
        "institutional_score": institutional_score,
        "max_drawdown": round(max_dd, 4) if pnls_f else None,
        "fabricated": False,
        "source": "real_completed_trades_only",
        "observe_only": True,
        "auto_applies": False,
    }
