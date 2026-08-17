"""Small-account eligibility — never increase risk to make a candidate testable."""

from __future__ import annotations

from typing import Any


def evaluate_small_account(
    *,
    equity: float,
    min_lot: float,
    risk_per_trade: float,
    margin_required: float,
    projected_drawdown_pct: float,
    portfolio_concentration_ok: bool,
    execution_cost_ok: bool,
    equity_floor: float = 50.0,
    max_risk_fraction: float = 0.02,
) -> dict[str, Any]:
    reasons: list[str] = []
    if equity < equity_floor:
        reasons.append("equity_too_small")
    if min_lot <= 0:
        reasons.append("invalid_min_lot")
    if risk_per_trade > equity * max_risk_fraction:
        reasons.append("risk_per_trade_too_high")
    if margin_required > equity:
        reasons.append("margin_exceeds_equity")
    if projected_drawdown_pct > 20.0:
        reasons.append("projected_drawdown_too_high")
    if not portfolio_concentration_ok:
        reasons.append("concentration")
    if not execution_cost_ok:
        reasons.append("execution_cost")
    if reasons:
        return {
            "result": "NOT_ELIGIBLE",
            "why_blocked": ",".join(reasons),
            "risk_increased_to_test": False,
            "eligible": False,
        }
    return {
        "result": "ELIGIBLE",
        "why_blocked": None,
        "risk_increased_to_test": False,
        "eligible": True,
    }
