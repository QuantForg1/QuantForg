"""Decision Engine — risk sizing & hard limit rejects (advisory)."""

from __future__ import annotations

from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def assess_decision_risk(
    *,
    account: dict[str, Any] | None,
    positions: list[dict[str, Any]],
    atr: float | None,
    price: float | None,
    side: str | None,
    max_risk_pct: float = 0.5,
    daily_loss_pct: float | None = None,
    weekly_loss_pct: float | None = None,
    max_drawdown_pct: float | None = None,
) -> dict[str, Any]:
    """Capital-preservation oriented sizing. Rejects over-limit ideas."""
    account = account or {}
    equity = _f(account.get("equity"))
    balance = _f(account.get("balance")) or equity
    margin = _f(account.get("margin"))
    free_margin = _f(account.get("free_margin") or account.get("margin_free"))

    rejects: list[str] = []
    warnings: list[str] = []

    if equity <= 0:
        return {
            "status": "unavailable",
            "accepted": False,
            "reason": "No equity snapshot for risk sizing",
            "autonomous_trading": False,
        }

    if daily_loss_pct is not None and daily_loss_pct <= -2.0:
        rejects.append(f"Daily loss {daily_loss_pct:.2f}% exceeds −2% limit")
    if weekly_loss_pct is not None and weekly_loss_pct <= -5.0:
        rejects.append(f"Weekly loss {weekly_loss_pct:.2f}% exceeds −5% limit")
    if max_drawdown_pct is not None and max_drawdown_pct >= 10.0:
        rejects.append(f"Open drawdown {max_drawdown_pct:.2f}% exceeds 10% soft cap")

    open_count = len(positions)
    if open_count >= 5:
        rejects.append(f"Too many open positions ({open_count}) — wait")
    elif open_count >= 3:
        warnings.append(f"{open_count} positions already open")

    floating = sum(_f(p.get("profit") or p.get("pnl")) for p in positions)
    if equity > 0 and floating / equity <= -0.03:
        rejects.append("Floating loss ≥ 3% of equity — capital preservation halt")

    max_risk_amount = equity * (max_risk_pct / 100.0)
    lot_size = None
    margin_est = None
    suggested_sl = None
    suggested_tp = None
    expected_rr = 2.0

    if atr and price and atr > 0:
        sl_dist = 1.5 * atr
        tp_dist = 3.0 * atr
        if side == "buy" or side == "Bullish":
            suggested_sl = round(price - sl_dist, 5)
            suggested_tp = round(price + tp_dist, 5)
        elif side == "sell" or side == "Bearish":
            suggested_sl = round(price + sl_dist, 5)
            suggested_tp = round(price - tp_dist, 5)
        # Crude lot sizing: risk_amount / (sl_dist * contract≈100k) — FX majors
        risk_per_lot = sl_dist * 100_000
        if risk_per_lot > 0:
            lot_size = round(max(0.01, min(1.0, max_risk_amount / risk_per_lot)), 2)
            margin_est = round(price * lot_size * 100_000 / max(_f(account.get("leverage"), 100), 1), 2)

    if free_margin >= 0 and equity > 0 and free_margin / equity < 0.15:
        rejects.append("Free margin under 15% of equity")

    if margin > 0 and equity / margin * 100 < 200:
        warnings.append("Margin level under 200%")

    accepted = len(rejects) == 0
    return {
        "status": "available",
        "accepted": accepted,
        "rejects": rejects,
        "warnings": warnings,
        "maximum_risk_pct": max_risk_pct,
        "maximum_risk_amount": round(max_risk_amount, 4),
        "lot_size": lot_size,
        "margin_estimate": margin_est,
        "portfolio_risk": {
            "open_positions": open_count,
            "floating_pnl": round(floating, 4),
            "equity": equity,
            "balance": balance,
        },
        "suggested_stop": suggested_sl,
        "suggested_tp": suggested_tp,
        "expected_rr": expected_rr,
        "daily_loss_pct": daily_loss_pct,
        "weekly_loss_pct": weekly_loss_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "autonomous_trading": False,
        "advisory_only": True,
    }
