"""Configurable thresholds for Market Intelligence Engine V1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class MarketIntelligenceConfig:
    """Policy knobs — never enables EXECUTION_ENABLED."""

    version: str = "market-intelligence-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Regime
    high_vol_atr_pct: Decimal = Decimal("1.50")
    low_vol_atr_pct: Decimal = Decimal("0.15")
    # Consensus
    min_consensus_confidence: Decimal = Decimal("60")
    min_agreeing_strategies: int = 2
    reject_conflicts: bool = True
    # Opportunity ranking
    min_opportunity_score: Decimal = Decimal("70")
    max_ranked_opportunities: int = 10
    # Execution quality gates (0-100)
    min_entry_quality: Decimal = Decimal("50")
    min_exit_quality: Decimal = Decimal("50")
    min_timing_quality: Decimal = Decimal("50")
    min_overall_execution_quality: Decimal = Decimal("55")
    # Portfolio risk
    daily_risk_budget_pct: Decimal = Decimal("3.00")
    max_allocation_pct: Decimal = Decimal("100")
    # AI health (0-100)
    min_decision_quality: Decimal = Decimal("50")
    min_execution_success: Decimal = Decimal("50")
    min_risk_discipline: Decimal = Decimal("60")
    min_system_reliability: Decimal = Decimal("70")
    # Hard locks
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_average_down: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_average_down", False)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "high_vol_atr_pct": str(self.high_vol_atr_pct),
            "low_vol_atr_pct": str(self.low_vol_atr_pct),
            "min_consensus_confidence": str(self.min_consensus_confidence),
            "min_agreeing_strategies": self.min_agreeing_strategies,
            "reject_conflicts": self.reject_conflicts,
            "min_opportunity_score": str(self.min_opportunity_score),
            "max_ranked_opportunities": self.max_ranked_opportunities,
            "min_entry_quality": str(self.min_entry_quality),
            "min_exit_quality": str(self.min_exit_quality),
            "min_timing_quality": str(self.min_timing_quality),
            "min_overall_execution_quality": str(
                self.min_overall_execution_quality
            ),
            "daily_risk_budget_pct": str(self.daily_risk_budget_pct),
            "max_allocation_pct": str(self.max_allocation_pct),
            "min_decision_quality": str(self.min_decision_quality),
            "min_execution_success": str(self.min_execution_success),
            "min_risk_discipline": str(self.min_risk_discipline),
            "min_system_reliability": str(self.min_system_reliability),
            "allow_martingale": False,
            "allow_grid": False,
            "allow_average_down": False,
            "mission": (
                "Institutional-grade market condition evaluation before any "
                "strategy may submit an order. Never promise profitability."
            ),
            "capabilities": [
                "market_regime_detection",
                "strategy_consensus",
                "opportunity_ranking",
                "execution_quality_review",
                "ai_trade_review",
                "portfolio_risk_dashboard",
                "ai_health_dashboard",
                "daily_validation_report",
            ],
        }


DEFAULT_MI_CONFIG = MarketIntelligenceConfig()
