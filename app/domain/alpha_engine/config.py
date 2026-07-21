"""Alpha Engine V1 — configurable thresholds (XAUUSD only)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class AlphaEngineConfig:
    """Policy knobs — never enables EXECUTION_ENABLED or bypasses Risk/Safety."""

    version: str = "alpha-engine-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Regime
    high_vol_atr_pct: Decimal = Decimal("1.50")
    low_vol_atr_pct: Decimal = Decimal("0.15")
    min_regime_score: Decimal = Decimal("55")
    # Liquidity
    max_spread_for_high_liquidity: Decimal = Decimal("0.50")
    max_spread_acceptable: Decimal = Decimal("2.00")
    min_liquidity_score: Decimal = Decimal("55")
    # Structure
    min_structure_score: Decimal = Decimal("55")
    # Order flow
    min_order_flow_score: Decimal = Decimal("50")
    # Confluence
    min_confluence_score: Decimal = Decimal("60")
    # Opportunity
    min_opportunity_score: Decimal = Decimal("65")
    max_ranked_opportunities: int = 10
    # Execution optimizer
    min_execution_score: Decimal = Decimal("55")
    # Exit intelligence
    min_exit_score: Decimal = Decimal("50")
    # Trade scoring
    min_trade_score: Decimal = Decimal("60")
    # Continuous evaluation
    min_continuous_score: Decimal = Decimal("50")
    # Composite
    min_composite_for_quality_ok: Decimal = Decimal("60")
    max_history: int = 200
    # Hard locks
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_order_send: bool = False
    promise_profitability: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allow_bypass_risk", False)
        object.__setattr__(self, "allow_bypass_safety", False)
        object.__setattr__(self, "allow_order_send", False)
        object.__setattr__(self, "promise_profitability", False)

    def update(self, updates: dict[str, object]) -> AlphaEngineConfig:
        locked = {
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_order_send",
            "promise_profitability",
            "symbol",
            "version",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key in data:
                data[key] = value
        return AlphaEngineConfig(
            high_vol_atr_pct=Decimal(str(data["high_vol_atr_pct"])),
            low_vol_atr_pct=Decimal(str(data["low_vol_atr_pct"])),
            min_regime_score=Decimal(str(data["min_regime_score"])),
            max_spread_for_high_liquidity=Decimal(
                str(data["max_spread_for_high_liquidity"])
            ),
            max_spread_acceptable=Decimal(str(data["max_spread_acceptable"])),
            min_liquidity_score=Decimal(str(data["min_liquidity_score"])),
            min_structure_score=Decimal(str(data["min_structure_score"])),
            min_order_flow_score=Decimal(str(data["min_order_flow_score"])),
            min_confluence_score=Decimal(str(data["min_confluence_score"])),
            min_opportunity_score=Decimal(str(data["min_opportunity_score"])),
            max_ranked_opportunities=int(data["max_ranked_opportunities"]),
            min_execution_score=Decimal(str(data["min_execution_score"])),
            min_exit_score=Decimal(str(data["min_exit_score"])),
            min_trade_score=Decimal(str(data["min_trade_score"])),
            min_continuous_score=Decimal(str(data["min_continuous_score"])),
            min_composite_for_quality_ok=Decimal(
                str(data["min_composite_for_quality_ok"])
            ),
            max_history=int(data["max_history"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "high_vol_atr_pct": str(self.high_vol_atr_pct),
            "low_vol_atr_pct": str(self.low_vol_atr_pct),
            "min_regime_score": str(self.min_regime_score),
            "max_spread_for_high_liquidity": str(
                self.max_spread_for_high_liquidity
            ),
            "max_spread_acceptable": str(self.max_spread_acceptable),
            "min_liquidity_score": str(self.min_liquidity_score),
            "min_structure_score": str(self.min_structure_score),
            "min_order_flow_score": str(self.min_order_flow_score),
            "min_confluence_score": str(self.min_confluence_score),
            "min_opportunity_score": str(self.min_opportunity_score),
            "max_ranked_opportunities": self.max_ranked_opportunities,
            "min_execution_score": str(self.min_execution_score),
            "min_exit_score": str(self.min_exit_score),
            "min_trade_score": str(self.min_trade_score),
            "min_continuous_score": str(self.min_continuous_score),
            "min_composite_for_quality_ok": str(
                self.min_composite_for_quality_ok
            ),
            "max_history": self.max_history,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_order_send": False,
            "promise_profitability": False,
        }


DEFAULT_ALPHA_CONFIG = AlphaEngineConfig()
