"""Promotion gate — Canary eligibility for institutional strategies."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.models import (
    AnalyticsReport,
    PromotionReport,
)
from app.domain.institutional_trading.research.monte_carlo import MonteCarloReport
from app.domain.institutional_trading.research.walk_forward import WalkForwardReport


@dataclass
class PromotionGate:
    """A strategy cannot reach Canary unless all institutional checks pass."""

    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)

    def evaluate(
        self,
        analytics: AnalyticsReport,
        *,
        walk_forward: WalkForwardReport | None = None,
        monte_carlo: MonteCarloReport | None = None,
        target: str = "canary",
    ) -> PromotionReport:
        checks: dict[str, bool] = {}
        reasons: list[str] = []

        checks["min_trades"] = analytics.trade_count >= self.config.promotion_min_trades
        if not checks["min_trades"]:
            reasons.append(
                f"trades {analytics.trade_count} < {self.config.promotion_min_trades}"
            )

        pf = analytics.profit_factor
        checks["profit_factor"] = (
            pf is not None and pf > self.config.promotion_min_profit_factor
        )
        if not checks["profit_factor"]:
            reasons.append(
                f"profit_factor {pf} not > {self.config.promotion_min_profit_factor}"
            )

        checks["max_drawdown"] = (
            analytics.max_drawdown_pct < self.config.promotion_max_drawdown_pct
        )
        if not checks["max_drawdown"]:
            reasons.append(
                f"max_drawdown {analytics.max_drawdown_pct}% "
                f">= {self.config.promotion_max_drawdown_pct}%"
            )

        checks["expectancy_positive"] = analytics.expectancy > 0
        if not checks["expectancy_positive"]:
            reasons.append(f"expectancy {analytics.expectancy} not positive")

        if self.config.promotion_require_walk_forward_pass:
            checks["walk_forward"] = bool(walk_forward and walk_forward.passed)
            if not checks["walk_forward"]:
                reasons.append("walk_forward PASS required")
        else:
            checks["walk_forward"] = True

        if self.config.promotion_require_monte_carlo_pass:
            checks["monte_carlo"] = bool(monte_carlo and monte_carlo.passed)
            if not checks["monte_carlo"]:
                reasons.append("monte_carlo PASS required")
        else:
            checks["monte_carlo"] = True

        eligible = all(checks.values())
        return PromotionReport(
            eligible=eligible,
            target=target,
            checks=checks,
            reasons=tuple(reasons),
            metrics_snapshot={
                "trade_count": analytics.trade_count,
                "profit_factor": str(pf) if pf is not None else None,
                "max_drawdown_pct": str(analytics.max_drawdown_pct),
                "expectancy": str(analytics.expectancy),
            },
        )
