"""Institutional Trading Brain V3 — configurable thresholds (XAUUSD only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class TradingBrainConfig:
    """All thresholds configurable — hard locks never lift."""

    version: str = "trading-brain-v3.0.0"
    symbol: str = GOLD_SYMBOL
    min_environment_score: Decimal = Decimal("50")
    min_opportunity_score: Decimal = Decimal("55")
    min_rank_score: Decimal = Decimal("60")
    min_challenge_pass_score: Decimal = Decimal("55")
    min_execution_readiness: Decimal = Decimal("60")
    min_discipline_score: Decimal = Decimal("65")
    max_spread: Decimal = Decimal("2.00")
    max_open_positions_soft: int = 3
    max_history: int = 200
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_order_send: bool = False
    promise_profitability: bool = False
    invent_market_data: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "environment_intelligence": True,
            "opportunity_discovery": True,
            "opportunity_ranking": True,
            "decision_challenge": True,
            "execution_readiness": True,
            "active_trade_supervisor": True,
            "post_trade_intelligence": True,
            "continuous_quality": True,
            "operator_advisor": True,
            "discipline_score": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_order_send = False
        self.promise_profitability = False
        self.invent_market_data = False

    def update(self, updates: dict[str, object]) -> TradingBrainConfig:
        locked = {
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_order_send",
            "promise_profitability",
            "invent_market_data",
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
                    if isinstance(fv, bool) and fk not in {
                        "bypass_risk",
                        "bypass_safety",
                        "order_send",
                        "promise_profit",
                    }:
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return TradingBrainConfig(
            min_environment_score=Decimal(str(data["min_environment_score"])),
            min_opportunity_score=Decimal(str(data["min_opportunity_score"])),
            min_rank_score=Decimal(str(data["min_rank_score"])),
            min_challenge_pass_score=Decimal(
                str(data["min_challenge_pass_score"])
            ),
            min_execution_readiness=Decimal(
                str(data["min_execution_readiness"])
            ),
            min_discipline_score=Decimal(str(data["min_discipline_score"])),
            max_spread=Decimal(str(data["max_spread"])),
            max_open_positions_soft=int(data["max_open_positions_soft"]),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_environment_score": str(self.min_environment_score),
            "min_opportunity_score": str(self.min_opportunity_score),
            "min_rank_score": str(self.min_rank_score),
            "min_challenge_pass_score": str(self.min_challenge_pass_score),
            "min_execution_readiness": str(self.min_execution_readiness),
            "min_discipline_score": str(self.min_discipline_score),
            "max_spread": str(self.max_spread),
            "max_open_positions_soft": self.max_open_positions_soft,
            "max_history": self.max_history,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_order_send": False,
            "promise_profitability": False,
            "invent_market_data": False,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_BRAIN_CONFIG = TradingBrainConfig()
