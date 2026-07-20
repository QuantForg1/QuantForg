"""Phase D PME configuration — separate from Phase A ITEConfig (untouched)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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
    partial_at_r: Decimal = Decimal("2.0")
    partial_close_pct: Decimal = Decimal("50")

    # Trailing (ATR-based, starts after 2R)
    trail_after_r: Decimal = Decimal("2.0")
    trail_atr_mult_normal: Decimal = Decimal("1.0")
    trail_atr_mult_high: Decimal = Decimal("1.5")
    trail_atr_mult_low: Decimal = Decimal("0.75")
    # ATR% of mid thresholds for regime
    atr_high_pct: Decimal = Decimal("1.5")
    atr_low_pct: Decimal = Decimal("0.4")

    # Time stop
    time_stop_minutes: int = 60
    time_stop_min_r: Decimal = Decimal("0.5")  # min favorable R within window
    # Allowed presets documented: 30 / 60 / 120

    # Spread emergency
    emergency_spread_max: Decimal = Decimal("5.00")

    # Volume rounding
    volume_step: Decimal = Decimal("0.01")
    min_volume: Decimal = Decimal("0.01")

    slippage: int = 10

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "config_version": self.config_version,
            "magic": self.magic,
            "comment_prefix": self.comment_prefix,
            "break_even_at_r": str(self.break_even_at_r),
            "break_even_offset_r": str(self.break_even_offset_r),
            "partial_at_r": str(self.partial_at_r),
            "partial_close_pct": str(self.partial_close_pct),
            "trail_after_r": str(self.trail_after_r),
            "time_stop_minutes": self.time_stop_minutes,
            "time_stop_min_r": str(self.time_stop_min_r),
            "emergency_spread_max": str(self.emergency_spread_max),
        }


DEFAULT_PME_CONFIG = PositionManagementConfig()
