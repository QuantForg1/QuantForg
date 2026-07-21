"""Active Trade Supervisor — advisory monitoring of supplied open trade."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def _try_dec(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def supervise_active_trade(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    _ = config
    trade = inp.active_trade
    if trade is None and inp.open_positions is None and inp.unrealized_pnl is None:
        return ModuleResult(
            module="active_trade_supervisor",
            status="empty",
            score=None,
            passed=None,
            recommendation="No active trade",
            reasons=("No active trade facts supplied — nothing to supervise",),
            details={},
        )

    reasons: list[str] = []
    details: dict[str, Any] = {}
    score = Decimal("60")

    if isinstance(trade, dict):
        details["trade_keys"] = sorted(str(k) for k in trade)[:20]
        side = trade.get("side")
        if side:
            reasons.append(f"Active side {side} observed")
        mfe = trade.get("mfe")
        mae = trade.get("mae")
        if mfe is not None:
            reasons.append(f"MFE {mfe} supplied")
            mfe_d = _try_dec(mfe)
            if mfe_d is not None and mfe_d > 0:
                score += Decimal("10")
        if mae is not None:
            reasons.append(f"MAE {mae} supplied")
            mae_d = _try_dec(mae)
            if mae_d is not None and mae_d < 0:
                score -= Decimal("10")
        if trade.get("structure_invalidated") is True:
            score = Decimal("25")
            reasons.append("Structure invalidated — advise review / exit plan")
    else:
        reasons.append("No structured active_trade payload")

    if inp.open_positions is not None:
        details["open_positions"] = inp.open_positions
        reasons.append(f"{inp.open_positions} open positions reported")
        if inp.open_positions >= 3:
            score -= Decimal("15")
            reasons.append("Multiple opens — concentration caution")

    if inp.unrealized_pnl is not None:
        details["unrealized_pnl"] = str(inp.unrealized_pnl)
        reasons.append(f"Unrealized PnL {inp.unrealized_pnl} (supplied)")
        if inp.unrealized_pnl < 0:
            score -= Decimal("10")
            reasons.append("Negative unrealized — supervise tightly")

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    reasons.append("Supervisor is advisory — does not close or send orders")
    reasons.append("Capital preservation focus; losses still possible")
    return ModuleResult(
        module="active_trade_supervisor",
        status="available",
        score=score,
        passed=score >= Decimal("50"),
        recommendation="Supervise" if score >= Decimal("40") else "Review exit",
        reasons=tuple(reasons),
        details=details,
    )
