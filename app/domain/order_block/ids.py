"""Deterministic identity helpers for order-block entities."""

from __future__ import annotations

from uuid import UUID, uuid5

_OB_NS = UUID("6ba7b820-9dad-11d1-80b4-00c04fd430c8")
_ZONE_NS = UUID("6ba7b821-9dad-11d1-80b4-00c04fd430c8")
_BREAKER_NS = UUID("6ba7b822-9dad-11d1-80b4-00c04fd430c8")
_MITIGATION_NS = UUID("6ba7b823-9dad-11d1-80b4-00c04fd430c8")


def order_block_id(
    symbol: str,
    timeframe: str,
    side: str,
    bar_index: int,
    low: str,
    high: str,
) -> UUID:
    return uuid5(
        _OB_NS,
        f"{symbol}:{timeframe}:{side}:{bar_index}:{low}:{high}",
    )


def zone_id(
    symbol: str,
    timeframe: str,
    low: str,
    high: str,
    bar_index: int,
) -> UUID:
    return uuid5(
        _ZONE_NS,
        f"{symbol}:{timeframe}:{bar_index}:{low}:{high}",
    )


def breaker_id(order_block: UUID, bar_index: int) -> UUID:
    return uuid5(_BREAKER_NS, f"{order_block}:{bar_index}")


def mitigation_id(order_block: UUID, bar_index: int, kind: str) -> UUID:
    return uuid5(_MITIGATION_NS, f"{order_block}:{bar_index}:{kind}")
