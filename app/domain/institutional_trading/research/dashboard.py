"""Operator dashboard aggregates — daily / weekly / monthly / yearly."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.research.models import (
    AnalyticsReport,
    ResearchTrade,
    SimulationResult,
)


@dataclass
class OperatorDashboard:
    """Build research operator views from stored simulation results."""

    def build(
        self,
        results: list[SimulationResult],
        *,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        trades: list[ResearchTrade] = []
        for r in results:
            trades.extend([t for t in r.trades if t.status == "closed"])

        by_day: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_week: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_year: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for t in trades:
            if not t.exit_time:
                continue
            by_day[t.exit_time.strftime("%Y-%m-%d")] += t.pnl
            by_week[t.exit_time.strftime("%Y-W%W")] += t.pnl
            by_month[t.exit_time.strftime("%Y-%m")] += t.pnl
            by_year[t.exit_time.strftime("%Y")] += t.pnl

        comparisons = [
            {
                "run_id": str(r.run_id),
                "strategy_version": r.strategy_version,
                "config_version": r.config_version,
                "input_hash": r.input_hash,
                "metrics": {
                    "trade_count": r.analytics.trade_count,
                    "win_rate": str(r.analytics.win_rate),
                    "profit_factor": (
                        str(r.analytics.profit_factor)
                        if r.analytics.profit_factor is not None
                        else None
                    ),
                    "max_drawdown_pct": str(r.analytics.max_drawdown_pct),
                    "expectancy": str(r.analytics.expectancy),
                    "sharpe": str(r.analytics.sharpe) if r.analytics.sharpe else None,
                },
            }
            for r in results
        ]

        return {
            "as_of": (as_of or datetime.now(UTC)).isoformat(),
            "daily": {k: str(v) for k, v in sorted(by_day.items())},
            "weekly": {k: str(v) for k, v in sorted(by_week.items())},
            "monthly": {k: str(v) for k, v in sorted(by_month.items())},
            "yearly": {k: str(v) for k, v in sorted(by_year.items())},
            "strategy_comparison": comparisons,
            "simulation_comparison": comparisons,
            "summary": {
                "simulations": len(results),
                "closed_trades": len(trades),
                "total_pnl": str(sum((t.pnl for t in trades), Decimal("0"))),
            },
        }

    @staticmethod
    def summarize_analytics(report: AnalyticsReport) -> dict[str, Any]:
        return report.to_dict()
