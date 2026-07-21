"""Decision Engine V1 configuration — XAUUSD, capital preservation first."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import MAX_SPREAD, coerce_max_spread


@dataclass(frozen=True, slots=True)
class DecisionEngineV1Config:
    """Policy knobs — never enables EXECUTION_ENABLED."""

    version: str = "institutional-ai-decision-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Confidence
    min_confidence: Decimal = Decimal("65")
    high_confidence: Decimal = Decimal("80")
    # Adaptive risk (% of equity)
    base_risk_pct: Decimal = Decimal("1.00")
    high_conf_risk_pct: Decimal = Decimal("1.00")
    mid_conf_risk_pct: Decimal = Decimal("0.50")
    low_conf_risk_pct: Decimal = Decimal("0.25")
    risk_floor_pct: Decimal = Decimal("0.15")
    # Strategy health
    min_health_score: Decimal = Decimal("50")
    auto_suspend_health_below: Decimal = Decimal("35")
    # Loss protection
    max_daily_drawdown_pct: Decimal = Decimal("3.00")
    max_consecutive_losses: int = 3
    max_spread: Decimal = MAX_SPREAD
    max_atr_pct_of_price: Decimal = Decimal("3.0")
    min_atr_pct_of_price: Decimal = Decimal("0.05")
    # Layers required to pass for TRADE_IDEA (Risk/Safety always required)
    require_trend: bool = True
    require_structure: bool = True
    require_liquidity: bool = False
    require_order_block: bool = False
    require_fvg: bool = False
    require_session: bool = True
    require_spread: bool = True
    # Dry-run is the only mode that this engine "executes"
    dry_run_default: bool = True
    # Hard locks
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_average_down: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_spread", coerce_max_spread(self.max_spread))
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_average_down", False)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_confidence": str(self.min_confidence),
            "high_confidence": str(self.high_confidence),
            "base_risk_pct": str(self.base_risk_pct),
            "high_conf_risk_pct": str(self.high_conf_risk_pct),
            "mid_conf_risk_pct": str(self.mid_conf_risk_pct),
            "low_conf_risk_pct": str(self.low_conf_risk_pct),
            "risk_floor_pct": str(self.risk_floor_pct),
            "min_health_score": str(self.min_health_score),
            "auto_suspend_health_below": str(self.auto_suspend_health_below),
            "max_daily_drawdown_pct": str(self.max_daily_drawdown_pct),
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_spread": str(self.max_spread),
            "max_atr_pct_of_price": str(self.max_atr_pct_of_price),
            "min_atr_pct_of_price": str(self.min_atr_pct_of_price),
            "dry_run_default": True,
            "allow_martingale": False,
            "allow_grid": False,
            "allow_average_down": False,
            "mission": (
                "Capital preservation and disciplined execution decisions. "
                "Never promise profitability."
            ),
            "pipeline": [
                "trend",
                "market_structure",
                "liquidity",
                "order_block",
                "fair_value_gap",
                "session",
                "spread",
                "risk",
                "safety",
            ],
        }


DEFAULT_DECISION_CONFIG = DecisionEngineV1Config()
