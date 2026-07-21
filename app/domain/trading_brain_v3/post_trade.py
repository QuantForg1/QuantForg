"""Post-Trade Intelligence — learn from supplied closed trades only."""

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


def evaluate_post_trade(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    _ = config
    trades = inp.closed_trades
    if trades is None:
        return ModuleResult(
            module="post_trade_intelligence",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="Await data",
            reasons=(
                "No closed trades supplied — never fabricates trade history",
            ),
            details={},
        )
    if len(trades) == 0:
        return ModuleResult(
            module="post_trade_intelligence",
            status="empty",
            score=None,
            passed=None,
            recommendation="Await data",
            reasons=("Closed trade list empty",),
            details={"count": 0},
        )

    reasons: list[str] = []
    pnls: list[Decimal] = []
    slips: list[Decimal] = []
    for row in trades:
        if not isinstance(row, dict):
            continue
        if row.get("pnl") is not None:
            pnl = _try_dec(row["pnl"])
            if pnl is not None:
                pnls.append(pnl)
        if row.get("slippage") is not None:
            slip = _try_dec(row["slippage"])
            if slip is not None:
                slips.append(slip)

    details: dict[str, Any] = {"count": len(trades)}
    score = Decimal("50")
    if pnls:
        wins = sum(1 for p in pnls if p > 0)
        details["trades_with_pnl"] = len(pnls)
        details["wins"] = wins
        details["win_rate"] = str(
            (Decimal(wins) / Decimal(len(pnls)) * Decimal("100")).quantize(
                Decimal("0.01")
            )
        )
        avg = (sum(pnls) / Decimal(len(pnls))).quantize(Decimal("0.01"))
        details["avg_pnl"] = str(avg)
        reasons.append(
            f"{len(pnls)} PnL samples — win_rate "
            f"{details['win_rate']}% (supplied)"
        )
        if avg >= 0:
            score += Decimal("15")
        else:
            score -= Decimal("10")
            reasons.append("Average PnL negative — reinforce discipline")
    else:
        reasons.append("Closed trades lack PnL fields — partial review")

    if slips:
        avg_slip = (sum(slips) / Decimal(len(slips))).quantize(Decimal("0.01"))
        details["avg_slippage"] = str(avg_slip)
        reasons.append(f"Avg slippage {avg_slip} (supplied)")
        if avg_slip > Decimal("0.5"):
            score -= Decimal("10")
            reasons.append("Elevated slippage — execution quality concern")

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    reasons.append("Post-trade insights are descriptive — not a profit promise")
    return ModuleResult(
        module="post_trade_intelligence",
        status="available",
        score=score,
        passed=score >= Decimal("50"),
        recommendation="Review lessons",
        reasons=tuple(reasons),
        details=details,
    )
