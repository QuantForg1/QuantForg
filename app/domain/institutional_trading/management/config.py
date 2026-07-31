"""Phase D PME configuration — separate from Phase A ITEConfig (untouched)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class PositionManagementConfig:
    """Deterministic position-management policy knobs."""

    symbol: str = GOLD_SYMBOL
    config_version: str = "ite-pme-v1.0.0"

    # Attribution — match Phase C tags without importing/editing Phase C logic
    magic: int = 260720
    comment_prefix: str = "ite:v1"

    # Break-even
    break_even_at_r: Decimal = Decimal("1.0")
    break_even_offset_r: Decimal = Decimal("0.2")  # +0.2R into profit

    # Partial
    partial_tp_enabled: bool = True
    partial_at_r: Decimal = Decimal("2.0")
    partial_close_pct: Decimal = Decimal("50")

    # Trailing (ATR-based, starts after 2R)
    trail_after_r: Decimal = Decimal("2.0")
    atr_trail_enabled: bool = True
    structure_trail_enabled: bool = False
    liquidity_trail_enabled: bool = False
    trail_atr_mult_normal: Decimal = Decimal("1.0")
    trail_atr_mult_high: Decimal = Decimal("1.5")
    trail_atr_mult_low: Decimal = Decimal("0.75")
    # ATR% of mid thresholds for regime
    atr_high_pct: Decimal = Decimal("1.5")
    atr_low_pct: Decimal = Decimal("0.4")

    # Time stop
    time_stop_minutes: int = 60
    time_stop_min_r: Decimal = Decimal("0.5")  # min favorable R within window
    # Absolute max hold for scalping — flatten regardless of R when set > 0
    absolute_max_hold_minutes: int = 0
    # Allowed presets documented: 30 / 60 / 120

    # Momentum fade exit
    momentum_fade_exit: bool = True
    momentum_fade_threshold: int = 40
    # Volatility collapse — edge disappears in compression
    volatility_collapse_exit: bool = True
    volatility_collapse_threshold: int = 25

    # Session-aware management (soft — does not change entry strategy)
    session_aware_management: bool = True
    session_profit_protect_at_r: Decimal = Decimal("1.5")
    # When session is weak (e.g. sydney/tokyo), tighten trail multiplier
    weak_session_trail_scale: Decimal = Decimal("0.85")
    # Second partial rung (scale-out) after first partial — optional
    second_partial_enabled: bool = True
    second_partial_at_r: Decimal = Decimal("3.0")
    second_partial_close_pct: Decimal = Decimal("25")

    # Spread emergency
    emergency_spread_max: Decimal = Decimal("5.00")

    # Volume rounding
    volume_step: Decimal = Decimal("0.01")
    min_volume: Decimal = Decimal("0.01")

    slippage: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "config_version": self.config_version,
            "magic": self.magic,
            "comment_prefix": self.comment_prefix,
            "break_even_at_r": str(self.break_even_at_r),
            "break_even_offset_r": str(self.break_even_offset_r),
            "partial_tp_enabled": self.partial_tp_enabled,
            "partial_at_r": str(self.partial_at_r),
            "partial_close_pct": str(self.partial_close_pct),
            "trail_after_r": str(self.trail_after_r),
            "atr_trail_enabled": self.atr_trail_enabled,
            "structure_trail_enabled": self.structure_trail_enabled,
            "liquidity_trail_enabled": self.liquidity_trail_enabled,
            "time_stop_minutes": self.time_stop_minutes,
            "time_stop_min_r": str(self.time_stop_min_r),
            "absolute_max_hold_minutes": self.absolute_max_hold_minutes,
            "momentum_fade_exit": self.momentum_fade_exit,
            "momentum_fade_threshold": self.momentum_fade_threshold,
            "volatility_collapse_exit": self.volatility_collapse_exit,
            "volatility_collapse_threshold": self.volatility_collapse_threshold,
            "session_aware_management": self.session_aware_management,
            "session_profit_protect_at_r": str(self.session_profit_protect_at_r),
            "weak_session_trail_scale": str(self.weak_session_trail_scale),
            "second_partial_enabled": self.second_partial_enabled,
            "second_partial_at_r": str(self.second_partial_at_r),
            "second_partial_close_pct": str(self.second_partial_close_pct),
            "emergency_spread_max": str(self.emergency_spread_max),
        }


DEFAULT_PME_CONFIG = PositionManagementConfig()
