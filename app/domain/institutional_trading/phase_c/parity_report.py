"""Formal live vs research parity report."""

from __future__ import annotations

from typing import Any, Mapping


def build_parity_report(
    *,
    research: Mapping[str, Any],
    live: Mapping[str, Any],
    min_sample: int = 20,
) -> dict[str, Any]:
    rn = int(research.get("trade_count") or research.get("trade_frequency") or 0)
    ln = int(live.get("trade_count") or live.get("trade_frequency") or 0)
    if rn < min_sample or ln < min_sample:
        state = "INSUFFICIENT_SAMPLE"
    else:
        re = research.get("expectancy") or research.get("avg_R")
        le = live.get("expectancy") or live.get("avg_R")
        if re is None or le is None:
            state = "INSUFFICIENT_SAMPLE"
        else:
            re_f, le_f = float(re), float(le)
            denom = abs(re_f) if abs(re_f) > 1e-9 else 1.0
            delta = (le_f - re_f) / denom
            if delta <= -0.5:
                state = "DEGRADED"
            elif abs(delta) <= 0.1:
                state = "ALIGNED"
            elif abs(delta) <= 0.3:
                state = "MILD_DEVIATION"
            else:
                state = "SIGNIFICANT_DEVIATION"

    def _pair(key: str) -> dict[str, Any]:
        return {"research": research.get(key), "live": live.get(key)}

    return {
        "trade_frequency": _pair("trade_count"),
        "expectancy": _pair("expectancy"),
        "avg_R": _pair("avg_R"),
        "drawdown": _pair("drawdown"),
        "MAE_R": _pair("MAE_R"),
        "MFE_R": _pair("MFE_R"),
        "spread_slippage": {
            "research": research.get("slippage"),
            "live": live.get("slippage"),
        },
        "regime_distribution": {
            "research": research.get("regime_distribution"),
            "live": live.get("regime_distribution"),
        },
        "state": state,
        "min_sample": int(min_sample),
        "auto_disable": False,
    }
