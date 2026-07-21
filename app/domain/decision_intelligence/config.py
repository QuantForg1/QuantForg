"""Configurable decision policies — never enables live force-execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class DecisionIntelligenceConfig:
    version: str = "decision-intelligence-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Confidence policies
    min_confidence: Decimal = Decimal("65")
    high_confidence: Decimal = Decimal("80")
    # Waterfall stage weights (informational; Risk/Safety always hard)
    require_signal: bool = True
    require_strategy_consensus: bool = True
    require_market_regime_ok: bool = True
    require_risk_engine: bool = True
    require_safety_engine: bool = True
    # Veto thresholds
    max_spread: Decimal = Decimal("2.00")
    max_daily_drawdown_pct: Decimal = Decimal("3.00")
    max_consecutive_losses: int = 3
    # Quality dashboard mins (0-100, supplied metrics only)
    min_decision_quality: Decimal = Decimal("50")
    # History
    max_history: int = 500
    # Hard locks
    allow_force_execution: bool = False
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_operator_force_approve: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allow_force_execution", False)
        object.__setattr__(self, "allow_bypass_risk", False)
        object.__setattr__(self, "allow_bypass_safety", False)
        object.__setattr__(self, "allow_operator_force_approve", False)
        object.__setattr__(self, "require_risk_engine", True)
        object.__setattr__(self, "require_safety_engine", True)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_confidence": str(self.min_confidence),
            "high_confidence": str(self.high_confidence),
            "require_signal": self.require_signal,
            "require_strategy_consensus": self.require_strategy_consensus,
            "require_market_regime_ok": self.require_market_regime_ok,
            "require_risk_engine": True,
            "require_safety_engine": True,
            "max_spread": str(self.max_spread),
            "max_daily_drawdown_pct": str(self.max_daily_drawdown_pct),
            "max_consecutive_losses": self.max_consecutive_losses,
            "min_decision_quality": str(self.min_decision_quality),
            "max_history": self.max_history,
            "allow_force_execution": False,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_operator_force_approve": False,
            "mission": (
                "Final institutional decision layer before execution. "
                "May reject trades; never force execution; never promise "
                "profitability."
            ),
            "capabilities": [
                "executive_decision_panel",
                "decision_waterfall",
                "trade_veto_system",
                "confidence_breakdown",
                "decision_history",
                "explainable_ai_summary",
                "decision_quality_dashboard",
                "operator_override_controls",
                "decision_replay",
                "configurable_decision_policies",
            ],
            "waterfall": [
                "signal",
                "strategy_consensus",
                "market_regime",
                "confidence",
                "veto_checks",
                "risk_engine",
                "safety_engine",
                "decision",
            ],
        }


DEFAULT_DI_CONFIG = DecisionIntelligenceConfig()
