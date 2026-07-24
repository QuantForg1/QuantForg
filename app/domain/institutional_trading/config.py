"""ITE v1 configuration — approved institutional defaults (2026-07-20)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class ITEConfig:
    """Versioned, deterministic engine configuration."""

    symbol: str = GOLD_SYMBOL
    config_version: str = "ite-v1.0.0"

    # Trading mode: swing (H4 stack) | scalping (H1→M1, no H4 required)
    trading_mode: str = "swing"

    # MTF hierarchy
    macro_bias_tf: Timeframe = Timeframe.H4
    primary_structure_tf: Timeframe = Timeframe.H1
    entry_confirmation_tf: Timeframe = Timeframe.M15
    execution_management_tf: Timeframe = Timeframe.M5

    # Confluence / quality gates
    min_confluence_score: int = 80
    high_confidence_score: int = 90
    min_trade_quality_score: int = 80

    # Risk (Phase B+ uses these; stored here for single source of truth)
    risk_per_trade_pct: Decimal = Decimal("1.0")
    max_daily_loss_pct: Decimal = Decimal("3.0")
    max_weekly_drawdown_pct: Decimal = Decimal("8.0")
    max_open_trades: int = 1
    max_consecutive_losses: int = 3

    # Trade management (Phase D)
    break_even_at_r: Decimal = Decimal("1.0")
    partial_at_r: Decimal = Decimal("2.0")
    partial_close_pct: Decimal = Decimal("50")
    trail_after_r: Decimal = Decimal("2.0")

    # Session filter
    allowed_sessions: tuple[MarketSession, ...] = (
        MarketSession.LONDON,
        MarketSession.NEW_YORK,
        MarketSession.LONDON_NY_OVERLAP,
    )

    # News protection — off until a reliable calendar feed is wired
    news_protection_enabled: bool = False
    news_blackout_minutes_before: int = 30
    news_blackout_minutes_after: int = 30
    high_impact_event_codes: tuple[str, ...] = (
        "NFP",
        "CPI",
        "FOMC",
        "INTEREST_RATE",
        "GDP",
        "PCE",
    )

    # Spread quality (points / price units — caller supplies live spread)
    max_spread_for_full_score: Decimal = Decimal("0.50")  # XAU typical tight
    max_spread_reject: Decimal = Decimal("2.00")

    candle_limit: int = 500
    swing_left: int = 2
    swing_right: int = 2

    simulation_fill_model: str = "next_bar_open"

    def timeframe_roles(self) -> dict[Timeframe, str]:
        return {
            self.macro_bias_tf: "macro_bias",
            self.primary_structure_tf: "primary_structure",
            self.entry_confirmation_tf: "entry_confirmation",
            self.execution_management_tf: "execution_management",
        }

    def analysis_timeframes(self) -> tuple[Timeframe, ...]:
        return (
            self.macro_bias_tf,
            self.primary_structure_tf,
            self.entry_confirmation_tf,
            self.execution_management_tf,
        )

    def is_scalping(self) -> bool:
        return str(self.trading_mode).lower() == "scalping"

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "config_version": self.config_version,
            "trading_mode": self.trading_mode,
            "macro_bias_tf": self.macro_bias_tf.value,
            "primary_structure_tf": self.primary_structure_tf.value,
            "entry_confirmation_tf": self.entry_confirmation_tf.value,
            "execution_management_tf": self.execution_management_tf.value,
            "min_confluence_score": self.min_confluence_score,
            "high_confidence_score": self.high_confidence_score,
            "min_trade_quality_score": self.min_trade_quality_score,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_weekly_drawdown_pct": str(self.max_weekly_drawdown_pct),
            "max_open_trades": self.max_open_trades,
            "max_consecutive_losses": self.max_consecutive_losses,
            "break_even_at_r": str(self.break_even_at_r),
            "partial_at_r": str(self.partial_at_r),
            "partial_close_pct": str(self.partial_close_pct),
            "trail_after_r": str(self.trail_after_r),
            "allowed_sessions": [s.value for s in self.allowed_sessions],
            "news_protection_enabled": self.news_protection_enabled,
            "simulation_fill_model": self.simulation_fill_model,
        }


DEFAULT_ITE_CONFIG = ITEConfig()
