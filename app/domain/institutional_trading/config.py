"""ITE v1 configuration — approved institutional defaults (2026-07-20)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_CEILING_PCT,
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_CONSECUTIVE_LOSSES,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_SL_RISK_USD,
    OWNER_MIN_REWARD_RISK,
    OWNER_MIN_SL_RISK_USD,
    OWNER_RISK_REFERENCE_USD,
    OWNER_SL_RISK_PCT,
    OWNER_WEEKLY_LOSS_PCT,
    max_aggregate_risk_usd,
)
from app.domain.institutional_trading.session_policy import TRADABLE_SESSIONS_24_7
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL

# Authoritative XAUUSD autonomous daily-loss percent:
# 48% of the UTC day's starting equity — see owner_live_limits.daily_loss_cap_usd.
# Boundary: loss > cap blocks; loss == cap does not.
MAX_DAILY_LOSS_PCT = OWNER_DAILY_LOSS_PCT
MAX_DAILY_LOSS_CEILING_PCT = OWNER_DAILY_LOSS_CEILING_PCT

# Planned SL-loss (not margin) at the reference capital: 20% of that equity.
# The book cap is 30% of the same reference, not 20% times the position count.
# No minimum floor. The live owner guard recomputes both caps from equity.
MIN_PLANNED_RISK_USD = OWNER_MIN_SL_RISK_USD
TARGET_PLANNED_RISK_USD = OWNER_MAX_SL_RISK_USD
TARGET_RISK_PER_TRADE_USD = TARGET_PLANNED_RISK_USD
MAX_PLANNED_SL_RISK_USD = OWNER_MAX_SL_RISK_USD
MAX_TOTAL_PLANNED_RISK_USD = max_aggregate_risk_usd(OWNER_RISK_REFERENCE_USD)
# Reward must clear the active 0.50 floor after costs. Never stretch TP.
MIN_REWARD_RISK = OWNER_MIN_REWARD_RISK
PREFERRED_REWARD_RISK = Decimal("1.50")
# Per-trade percent ceiling (20% of the risk reference).
RISK_PER_TRADE_CEILING_PCT = OWNER_SL_RISK_PCT


def coerce_max_daily_loss_pct(value: Decimal) -> Decimal:
    """Reject non-positive values and anything above the hard ceiling."""
    cap = Decimal(str(value))
    if cap <= 0 or cap > MAX_DAILY_LOSS_CEILING_PCT:
        raise ValueError(
            f"max_daily_loss_pct must be in (0, {MAX_DAILY_LOSS_CEILING_PCT}]"
        )
    return cap


def coerce_risk_per_trade_pct(value: Decimal) -> Decimal:
    """Reject non-positive values and anything above the per-trade ceiling."""
    pct = Decimal(str(value))
    if pct <= 0 or pct > RISK_PER_TRADE_CEILING_PCT:
        raise ValueError(
            f"risk_per_trade_pct must be in (0, {RISK_PER_TRADE_CEILING_PCT}]"
        )
    return pct


@dataclass(frozen=True, slots=True)
class ITEConfig:
    """Versioned, deterministic engine configuration."""

    symbol: str = GOLD_SYMBOL
    config_version: str = "ite-v2.2.0"

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
    min_planned_risk_usd: Decimal = MIN_PLANNED_RISK_USD
    target_risk_per_trade_usd: Decimal = TARGET_PLANNED_RISK_USD
    max_planned_sl_risk_usd: Decimal = MAX_PLANNED_SL_RISK_USD
    max_total_planned_risk_usd: Decimal = MAX_TOTAL_PLANNED_RISK_USD
    max_daily_loss_pct: Decimal = MAX_DAILY_LOSS_PCT
    max_weekly_drawdown_pct: Decimal = OWNER_WEEKLY_LOSS_PCT
    max_open_trades: int = OWNER_MAX_OPEN_POSITIONS
    max_consecutive_losses: int = OWNER_MAX_CONSECUTIVE_LOSSES

    # Trade management (Phase D)
    break_even_at_r: Decimal = Decimal("1.0")
    partial_at_r: Decimal = Decimal("2.0")
    partial_close_pct: Decimal = Decimal("50")
    trail_after_r: Decimal = Decimal("2.0")

    # Session filter — 24/7 named windows; off-hours/weekend still blocked
    allowed_sessions: tuple[MarketSession, ...] = TRADABLE_SESSIONS_24_7

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

    def __post_init__(self) -> None:
        # Owner ceilings — a config may be stricter, never looser.
        coerce_max_daily_loss_pct(self.max_daily_loss_pct)
        coerce_risk_per_trade_pct(self.risk_per_trade_pct)
        if self.max_planned_sl_risk_usd > OWNER_MAX_SL_RISK_USD:
            raise ValueError(
                f"max_planned_sl_risk_usd must be <= {OWNER_MAX_SL_RISK_USD}"
            )
        if not 1 <= self.max_open_trades <= OWNER_MAX_OPEN_POSITIONS:
            raise ValueError(
                f"max_open_trades must be in [1, {OWNER_MAX_OPEN_POSITIONS}]"
            )

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
        return str(self.trading_mode).lower() in {"scalping", "alpha"}

    def to_dict(self) -> dict[str, Any]:
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
            "min_planned_risk_usd": str(self.min_planned_risk_usd),
            "target_risk_per_trade_usd": str(self.target_risk_per_trade_usd),
            "max_planned_sl_risk_usd": str(self.max_planned_sl_risk_usd),
            "max_total_planned_risk_usd": str(self.max_total_planned_risk_usd),
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
