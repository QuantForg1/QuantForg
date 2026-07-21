"""Strategy performance + health score + automatic pause."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.ai_trading_robot.config import RobotV1Config


@dataclass(frozen=True, slots=True)
class StrategyPerformance:
    strategy_id: str
    trades: int
    wins: int
    losses: int
    win_rate: Decimal
    profit_factor: Decimal | None
    expectancy: Decimal | None
    avg_r: Decimal | None
    net_pnl: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": str(self.win_rate),
            "profit_factor": (
                str(self.profit_factor) if self.profit_factor is not None else None
            ),
            "expectancy": (
                str(self.expectancy) if self.expectancy is not None else None
            ),
            "avg_r": str(self.avg_r) if self.avg_r is not None else None,
            "net_pnl": str(self.net_pnl),
        }


@dataclass(frozen=True, slots=True)
class StrategyHealth:
    strategy_id: str
    score: Decimal
    status: str  # healthy | watch | pause
    auto_pause: bool
    reasons: tuple[str, ...]
    performance: StrategyPerformance

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "score": str(self.score),
            "status": self.status,
            "auto_pause": self.auto_pause,
            "reasons": list(self.reasons),
            "performance": self.performance.to_dict(),
        }


def compute_strategy_performance(
    *,
    strategy_id: str,
    closed_pnls: list[Decimal],
    r_multiples: list[Decimal] | None = None,
) -> StrategyPerformance:
    trades = len(closed_pnls)
    wins = sum(1 for p in closed_pnls if p > 0)
    losses = sum(1 for p in closed_pnls if p < 0)
    win_rate = (
        (Decimal(wins) / Decimal(trades) * Decimal("100")).quantize(Decimal("0.01"))
        if trades
        else Decimal("0")
    )
    gross_win = sum((p for p in closed_pnls if p > 0), Decimal("0"))
    gross_loss = abs(sum((p for p in closed_pnls if p < 0), Decimal("0")))
    pf: Decimal | None
    if gross_loss > 0:
        pf = (gross_win / gross_loss).quantize(Decimal("0.01"))
    elif gross_win > 0:
        pf = Decimal("999")
    else:
        pf = None
    net = sum(closed_pnls, Decimal("0"))
    expectancy = (net / Decimal(trades)).quantize(Decimal("0.01")) if trades else None
    avg_r = None
    if r_multiples:
        avg_r = (sum(r_multiples, Decimal("0")) / Decimal(len(r_multiples))).quantize(
            Decimal("0.01")
        )
    return StrategyPerformance(
        strategy_id=strategy_id,
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        profit_factor=pf,
        expectancy=expectancy,
        avg_r=avg_r,
        net_pnl=net.quantize(Decimal("0.01")),
    )


def score_strategy_health(
    config: RobotV1Config, performance: StrategyPerformance
) -> StrategyHealth:
    """Health 0-100. Auto-pause when below auto_pause_health_below."""
    reasons: list[str] = []
    if performance.trades == 0:
        return StrategyHealth(
            strategy_id=performance.strategy_id,
            score=Decimal("50"),
            status="watch",
            auto_pause=False,
            reasons=("No closed trades yet — neutral health.",),
            performance=performance,
        )

    score = Decimal("40")
    # Win rate contribution
    score += (performance.win_rate - Decimal("40")) * Decimal("0.4")
    if performance.profit_factor is not None:
        if performance.profit_factor >= Decimal("1.5"):
            score += Decimal("15")
        elif performance.profit_factor >= Decimal("1.0"):
            score += Decimal("5")
        else:
            score -= Decimal("20")
            reasons.append(f"Profit factor {performance.profit_factor} < 1.0")
    if performance.expectancy is not None and performance.expectancy < 0:
        score -= Decimal("15")
        reasons.append("Negative expectancy.")
    if performance.net_pnl < 0:
        score -= Decimal("10")
        reasons.append("Net PnL negative.")
    # Sample size caution
    if performance.trades < 10:
        score -= Decimal("5")
        reasons.append("Small sample — treat health cautiously.")

    score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
    auto_pause = score < config.auto_pause_health_below
    if auto_pause:
        status = "pause"
        reasons.append(
            f"Health {score} below auto-pause threshold "
            f"{config.auto_pause_health_below}."
        )
    elif score < config.min_health_score:
        status = "watch"
        reasons.append(f"Health {score} below min {config.min_health_score}.")
    else:
        status = "healthy"

    return StrategyHealth(
        strategy_id=performance.strategy_id,
        score=score,
        status=status,
        auto_pause=auto_pause,
        reasons=tuple(reasons),
        performance=performance,
    )
