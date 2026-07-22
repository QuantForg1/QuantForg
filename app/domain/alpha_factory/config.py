"""Alpha Factory — isolated research config (never touches production)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL

STRATEGY_FAMILIES = (
    "SMC",
    "Liquidity",
    "Breakout",
    "Reversal",
    "Mean Reversion",
    "Hybrid",
    "Experimental",
)

PROMOTION_STAGES = (
    "Development",
    "Replay",
    "Paper Trading",
    "Research Approval",
    "Risk Review",
    "Operator Approval",
    "Production Candidate",
    "Production",
)

REPLAY_TIMEFRAMES = ("1m", "5m", "15m")


@dataclass
class AlphaFactoryConfig:
    version: str = "alpha-factory-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_trades_for_score: int = 20
    min_trades_for_benchmark: int = 10
    max_experiments: int = 500
    max_history: int = 300
    # Hard locks — research isolation
    allow_order_send: bool = False
    allow_modify_live_strategy: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    allow_modify_decision_engine: bool = False
    allow_modify_execution_pipeline: bool = False
    allow_modify_auto_trading: bool = False
    allow_automatic_promotion: bool = False
    invent_market_data: bool = False
    invent_metrics: bool = False
    promise_profitability: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "research_workspace": True,
            "strategy_laboratory": True,
            "replay_engine": True,
            "paper_trading_pipeline": True,
            "benchmark_engine": True,
            "promotion_workflow": True,
            "experiment_history": True,
            "research_dashboard": True,
            "alpha_score": True,
            "promotion_report": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_modify_live_strategy = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.allow_modify_decision_engine = False
        self.allow_modify_execution_pipeline = False
        self.allow_modify_auto_trading = False
        self.allow_automatic_promotion = False
        self.invent_market_data = False
        self.invent_metrics = False
        self.promise_profitability = False

    def update(self, updates: dict[str, object]) -> AlphaFactoryConfig:
        locked = {
            "allow_order_send",
            "allow_modify_live_strategy",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "allow_modify_decision_engine",
            "allow_modify_execution_pipeline",
            "allow_modify_auto_trading",
            "allow_automatic_promotion",
            "invent_market_data",
            "invent_metrics",
            "promise_profitability",
            "symbol",
            "version",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key == "feature_flags" and isinstance(value, dict):
                flags = dict(data["feature_flags"])  # type: ignore[arg-type]
                for fk, fv in value.items():
                    if isinstance(fv, bool):
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return AlphaFactoryConfig(
            min_trades_for_score=int(data["min_trades_for_score"]),
            min_trades_for_benchmark=int(data["min_trades_for_benchmark"]),
            max_experiments=int(data["max_experiments"]),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_trades_for_score": self.min_trades_for_score,
            "min_trades_for_benchmark": self.min_trades_for_benchmark,
            "max_experiments": self.max_experiments,
            "max_history": self.max_history,
            "strategy_families": list(STRATEGY_FAMILIES),
            "promotion_stages": list(PROMOTION_STAGES),
            "replay_timeframes": list(REPLAY_TIMEFRAMES),
            "allow_order_send": False,
            "allow_modify_live_strategy": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "allow_modify_decision_engine": False,
            "allow_modify_execution_pipeline": False,
            "allow_modify_auto_trading": False,
            "allow_automatic_promotion": False,
            "invent_market_data": False,
            "invent_metrics": False,
            "promise_profitability": False,
            "feature_flags": dict(self.feature_flags),
            "min_alpha_hint": str(Decimal("60")),
        }


DEFAULT_ALPHA_FACTORY_CONFIG = AlphaFactoryConfig()
