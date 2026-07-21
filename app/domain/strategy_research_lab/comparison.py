"""Strategy Comparison Dashboard — from supplied run metrics only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StrategyRunMetrics:
    strategy_key: str
    run_id: str
    profit_factor: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    trade_count: int | None = None
    win_rate: Decimal | None = None
    net_pnl: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    strategy_key: str
    run_id: str
    score: Decimal
    metrics: dict[str, object]
    rank: int

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "run_id": self.run_id,
            "score": str(self.score),
            "metrics": self.metrics,
            "rank": self.rank,
        }


def compare_strategy_runs(
    runs: tuple[StrategyRunMetrics, ...],
) -> dict[str, object]:
    if not runs:
        return {
            "rows": [],
            "leader": None,
            "status": "unavailable",
            "reason": "No run metrics supplied — nothing to compare.",
            "note": "Never invents comparison metrics.",
        }

    scored: list[tuple[Decimal, StrategyRunMetrics]] = []
    for run in runs:
        score = Decimal("50")
        if run.profit_factor is not None:
            score += min(
                Decimal("20"),
                (run.profit_factor - Decimal("1")) * Decimal("10"),
            )
        if run.sharpe is not None:
            score += min(Decimal("15"), run.sharpe * Decimal("10"))
        if run.max_drawdown_pct is not None:
            score -= min(Decimal("20"), run.max_drawdown_pct / Decimal("2"))
        if run.win_rate is not None:
            score += (run.win_rate - Decimal("50")) * Decimal("0.2")
        score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
        scored.append((score, run))

    scored.sort(key=lambda x: x[0], reverse=True)
    rows: list[ComparisonRow] = []
    for i, (score, run) in enumerate(scored, start=1):
        rows.append(
            ComparisonRow(
                strategy_key=run.strategy_key,
                run_id=run.run_id,
                score=score,
                metrics={
                    "profit_factor": (
                        str(run.profit_factor)
                        if run.profit_factor is not None
                        else None
                    ),
                    "sharpe": str(run.sharpe) if run.sharpe is not None else None,
                    "max_drawdown_pct": (
                        str(run.max_drawdown_pct)
                        if run.max_drawdown_pct is not None
                        else None
                    ),
                    "trade_count": run.trade_count,
                    "win_rate": str(run.win_rate) if run.win_rate is not None else None,
                    "net_pnl": str(run.net_pnl) if run.net_pnl is not None else None,
                },
                rank=i,
            )
        )

    return {
        "rows": [r.to_dict() for r in rows],
        "leader": rows[0].to_dict() if rows else None,
        "status": "available",
        "reason": f"Compared {len(rows)} supplied lab runs.",
        "note": "Lab comparison only — not production performance.",
    }
