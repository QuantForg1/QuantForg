"""Offline validation gate for strategy influence — never auto-enables LIVE.

Compares reported backtest / walk-forward metrics against conservative floors.
Does not run broker order_send. Does not fabricate results. A pass here only
marks a strategy as *eligible for SOE influence consideration* after human
review — never APPROVED_FOR_LIVE automatically (Phase C promotion rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BacktestGateThresholds:
    min_closed_trades: int = 30
    min_profit_factor: float = 1.15
    min_expectancy: float = 0.0
    max_drawdown_pct: float = 15.0
    min_win_rate_pct: float = 40.0
    require_oos_pass: bool = True
    require_walk_forward_pass: bool = True


DEFAULT_THRESHOLDS = BacktestGateThresholds()


def evaluate_backtest_gate(
    metrics: dict[str, Any] | None,
    *,
    thresholds: BacktestGateThresholds = DEFAULT_THRESHOLDS,
    strategy_id: str = "",
) -> dict[str, Any]:
    """Return pass/fail with reasons. Missing metrics → fail closed."""
    m = dict(metrics or {})
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    def _f(key: str) -> float | None:
        raw = m.get(key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    closed = int(m.get("closed_trades") or m.get("trades") or 0)
    checks["sample_size"] = closed >= thresholds.min_closed_trades
    if not checks["sample_size"]:
        reasons.append(
            f"closed_trades {closed} < {thresholds.min_closed_trades} "
            "(insufficient for validation claim)"
        )

    pf = _f("profit_factor")
    checks["profit_factor"] = pf is not None and pf >= thresholds.min_profit_factor
    if not checks["profit_factor"]:
        reasons.append(
            f"profit_factor {pf} < {thresholds.min_profit_factor} or missing"
        )

    exp = _f("expectancy")
    checks["expectancy"] = exp is not None and exp >= thresholds.min_expectancy
    if not checks["expectancy"]:
        reasons.append(f"expectancy {exp} < {thresholds.min_expectancy} or missing")

    dd = _f("max_drawdown_pct")
    if dd is None:
        dd = _f("max_drawdown")
    checks["drawdown"] = dd is not None and dd <= thresholds.max_drawdown_pct
    if not checks["drawdown"]:
        reasons.append(f"max_drawdown {dd} > {thresholds.max_drawdown_pct} or missing")

    wr = _f("win_rate")
    if wr is not None and wr <= 1.0:
        wr = wr * 100.0
    checks["win_rate"] = wr is not None and wr >= thresholds.min_win_rate_pct
    if not checks["win_rate"]:
        reasons.append(f"win_rate {wr} < {thresholds.min_win_rate_pct} or missing")

    if thresholds.require_oos_pass:
        oos = m.get("oos_passed")
        checks["oos"] = oos is True
        if not checks["oos"]:
            reasons.append("out-of-sample pass required and missing/false")
    else:
        checks["oos"] = True

    if thresholds.require_walk_forward_pass:
        wf = m.get("walk_forward_passed")
        checks["walk_forward"] = wf is True
        if not checks["walk_forward"]:
            reasons.append("walk-forward pass required and missing/false")
    else:
        checks["walk_forward"] = True

    # Overfit / leakage flags if provided by research platform
    if m.get("overfit_flag") is True or m.get("data_leakage_flag") is True:
        checks["integrity"] = False
        reasons.append("overfit or data_leakage flag set — fail closed")
    else:
        checks["integrity"] = True

    passed = all(checks.values())
    return {
        "strategy_id": strategy_id or m.get("strategy_id"),
        "passed": passed,
        "checks": checks,
        "reasons": reasons,
        "metrics_used": {
            "closed_trades": closed,
            "profit_factor": pf,
            "expectancy": exp,
            "max_drawdown_pct": dd,
            "win_rate_pct": wr,
            "oos_passed": m.get("oos_passed"),
            "walk_forward_passed": m.get("walk_forward_passed"),
        },
        "live_auto_authorize": False,
        "note": (
            "Gate pass ≠ live authorization. Owner approval + Risk/OMS/MT5 "
            "gates + paper validation still required. Never guarantee profits."
        ),
        "disclaimer": "Historical data does not guarantee future profitability.",
    }
