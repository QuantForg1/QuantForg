"""Strategy Research Lab configuration — lab-only, never live execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class StrategyLabConfig:
    version: str = "strategy-research-lab-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Scorecard thresholds (supplied metrics only)
    min_scorecard: Decimal = Decimal("60")
    min_profit_factor: Decimal = Decimal("1.20")
    min_sharpe: Decimal = Decimal("0.50")
    max_drawdown_pct: Decimal = Decimal("20")
    min_trades: int = 20
    # Promotion
    require_operator_approval: bool = True
    require_scorecard_pass: bool = True
    require_validation_pass: bool = True
    # Experiments
    max_experiments_per_batch: int = 50
    # Replay
    max_replay_bars: int = 5000
    # Hard isolation
    allows_broker_orders: bool = False
    affects_production_positions: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allows_broker_orders", False)
        object.__setattr__(self, "affects_production_positions", False)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_scorecard": str(self.min_scorecard),
            "min_profit_factor": str(self.min_profit_factor),
            "min_sharpe": str(self.min_sharpe),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "min_trades": self.min_trades,
            "require_operator_approval": self.require_operator_approval,
            "require_scorecard_pass": self.require_scorecard_pass,
            "require_validation_pass": self.require_validation_pass,
            "max_experiments_per_batch": self.max_experiments_per_batch,
            "max_replay_bars": self.max_replay_bars,
            "allows_broker_orders": False,
            "affects_production_positions": False,
            "mission": (
                "Validate and promote trading strategies before production. "
                "Never promise profitability. Never submit broker orders."
            ),
            "capabilities": [
                "strategy_registry",
                "historical_replay",
                "strategy_comparison",
                "parameter_experiments",
                "promotion_workflow",
                "strategy_scorecards",
                "explainable_validation_reports",
                "operator_approval",
                "version_history",
                "promotion_dashboard",
            ],
            "isolation": {
                "separated_from_live_execution": True,
                "never_order_send": True,
                "paper_and_replay_only": True,
                "no_mock_production_metrics": True,
            },
        }


DEFAULT_LAB_CONFIG = StrategyLabConfig()
