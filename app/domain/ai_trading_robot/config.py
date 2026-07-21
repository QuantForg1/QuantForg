"""Robot V1 configuration — XAUUSD desk, capital preservation first."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import MAX_SPREAD, coerce_max_spread


@dataclass(frozen=True, slots=True)
class RobotV1Config:
    """Policy knobs for AI Trading Robot V1 (never enables EXECUTION_ENABLED)."""

    version: str = "ai-robot-v1.0.0"
    symbol: str = GOLD_SYMBOL
    # Dynamic sizing
    base_risk_pct: Decimal = Decimal("1.00")
    risk_floor_pct: Decimal = Decimal("0.25")
    reduction_per_consecutive_loss: Decimal = Decimal("0.25")
    reduction_per_drawdown_pct: Decimal = Decimal("0.10")
    # Daily drawdown protection
    max_daily_drawdown_pct: Decimal = Decimal("3.00")
    # Consecutive loss protection
    max_consecutive_losses: int = 3
    cooldown_minutes_after_streak: int = 60
    # Filters
    max_spread: Decimal = MAX_SPREAD
    max_atr_pct_of_price: Decimal = Decimal("3.0")
    min_atr_pct_of_price: Decimal = Decimal("0.05")
    allowed_sessions: tuple[str, ...] = (
        "london",
        "new_york",
        "london_ny_overlap",
    )
    news_filter_enabled: bool = True
    # AI confidence
    min_confidence: Decimal = Decimal("60")
    # Strategy health
    min_health_score: Decimal = Decimal("50")
    auto_pause_health_below: Decimal = Decimal("35")
    # Smart trade management (PME policy — advisory defaults for operators)
    break_even_at_r: Decimal = Decimal("1.0")
    partial_tp_at_r: Decimal = Decimal("2.0")
    partial_tp_pct: Decimal = Decimal("50")
    trail_after_r: Decimal = Decimal("2.0")
    # Session manager
    manage_positions_off_session: bool = True
    # Forbidden
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_average_losers: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_spread", coerce_max_spread(self.max_spread))
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        # Hard-lock forbidden techniques
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_average_losers", False)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "base_risk_pct": str(self.base_risk_pct),
            "risk_floor_pct": str(self.risk_floor_pct),
            "max_daily_drawdown_pct": str(self.max_daily_drawdown_pct),
            "max_consecutive_losses": self.max_consecutive_losses,
            "cooldown_minutes_after_streak": self.cooldown_minutes_after_streak,
            "max_spread": str(self.max_spread),
            "max_atr_pct_of_price": str(self.max_atr_pct_of_price),
            "min_atr_pct_of_price": str(self.min_atr_pct_of_price),
            "allowed_sessions": list(self.allowed_sessions),
            "news_filter_enabled": self.news_filter_enabled,
            "min_confidence": str(self.min_confidence),
            "min_health_score": str(self.min_health_score),
            "auto_pause_health_below": str(self.auto_pause_health_below),
            "break_even_at_r": str(self.break_even_at_r),
            "partial_tp_at_r": str(self.partial_tp_at_r),
            "partial_tp_pct": str(self.partial_tp_pct),
            "trail_after_r": str(self.trail_after_r),
            "manage_positions_off_session": self.manage_positions_off_session,
            "allow_martingale": False,
            "allow_grid": False,
            "allow_average_losers": False,
            "mission": (
                "Maximize discipline and capital preservation. "
                "Never promise profitability."
            ),
            "pipeline": [
                "Signal",
                "Strategy Validation",
                "Risk Engine",
                "Safety Engine",
                "Execution",
            ],
        }


DEFAULT_ROBOT_CONFIG = RobotV1Config()
