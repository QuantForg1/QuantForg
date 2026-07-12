"""Deterministic identity helpers for fair-value-gap entities."""

from __future__ import annotations

from uuid import UUID, uuid5

_FVG_NS = UUID("6ba7b830-9dad-11d1-80b4-00c04fd430c8")
_ZONE_NS = UUID("6ba7b831-9dad-11d1-80b4-00c04fd430c8")
_FILL_NS = UUID("6ba7b832-9dad-11d1-80b4-00c04fd430c8")


def fvg_id(
    symbol: str,
    timeframe: str,
    side: str,
    middle_bar_index: int,
    low: str,
    high: str,
) -> UUID:
    return uuid5(
        _FVG_NS,
        f"{symbol}:{timeframe}:{side}:{middle_bar_index}:{low}:{high}",
    )


def zone_id(
    symbol: str,
    timeframe: str,
    middle_bar_index: int,
    low: str,
    high: str,
) -> UUID:
    return uuid5(
        _ZONE_NS,
        f"{symbol}:{timeframe}:{middle_bar_index}:{low}:{high}",
    )


def fill_id(gap: UUID, bar_index: int, kind: str) -> UUID:
    return uuid5(_FILL_NS, f"{gap}:{bar_index}:{kind}")
