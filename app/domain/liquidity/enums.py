"""Liquidity-engine enumerations.

Why these exist
---------------
Shared vocabulary for buy/sell-side liquidity pools, zones, and sweeps —
without encoding trade signals or classic indicators.
Distinct from market_context ``LiquidityLevel`` / ``LiquidityProfile``
(session regime), which remain unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class LiquiditySide(StrEnum):
    """Which side of price resting liquidity sits on."""

    BUY_SIDE = "buy_side"  # equal lows / demand below
    SELL_SIDE = "sell_side"  # equal highs / supply above


class LiquidityPoolStatus(StrEnum):
    """Lifecycle status of a liquidity pool."""

    ACTIVE = "active"
    SWEPT = "swept"


class LiquidityStateKind(StrEnum):
    """Qualitative liquidity bias for a symbol/timeframe."""

    UNKNOWN = "unknown"
    BALANCED = "balanced"
    BUY_SIDE_HEAVY = "buy_side_heavy"
    SELL_SIDE_HEAVY = "sell_side_heavy"
    BUY_SIDE_SWEPT = "buy_side_swept"
    SELL_SIDE_SWEPT = "sell_side_swept"


class SweepKind(StrEnum):
    """How a pool was taken."""

    HIGH_SWEEP = "high_sweep"  # took sell-side (equal highs)
    LOW_SWEEP = "low_sweep"  # took buy-side (equal lows)
