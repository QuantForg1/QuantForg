"""Validation — compare backtest vs live; only keep measurable improvements."""

from __future__ import annotations

from typing import Any


def compare_backtest_vs_live(
    *,
    backtest: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, Any]:
    """Return whether candidate metrics improve WR / PF / DD / Avg RR."""

    def _f(d: dict[str, Any], *keys: str) -> float | None:
        for k in keys:
            if d.get(k) is not None:
                try:
                    return float(d[k])
                except (TypeError, ValueError):
                    continue
        return None

    metrics = ("win_rate", "profit_factor", "drawdown", "average_rr")
    deltas: dict[str, Any] = {}
    improves = 0
    for m in metrics:
        b = _f(backtest, m, m.replace("_", ""))
        live_v = _f(live, m, m.replace("_", ""))
        if b is None or live_v is None:
            deltas[m] = {"backtest": b, "live": live_v, "improved": None}
            continue
        # Lower drawdown is better; others higher is better
        improved = b <= live_v if m == "drawdown" else b >= live_v
        if improved:
            improves += 1
        deltas[m] = {
            "backtest": b,
            "live": live_v,
            "improved": improved,
            "delta": round(b - live_v, 4),
        }

    deploy_ok = improves >= 3 and (
        deltas.get("drawdown", {}).get("improved") is not False
    )
    return {
        "deltas": deltas,
        "improves_count": improves,
        "recommend_deploy": deploy_ok,
        "message": (
            "Deploy candidate — measurable improvement on ≥3 of WR/PF/DD/RR"
            if deploy_ok
            else "Do not deploy — insufficient measurable improvement vs live"
        ),
        "never_bypass_risk": True,
    }
