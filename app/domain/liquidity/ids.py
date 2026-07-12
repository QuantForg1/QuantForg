"""Shared deterministic identity helpers for liquidity entities."""

from __future__ import annotations

from uuid import UUID, uuid5

# Stable namespaces (DNS OID family) — distinct keys per entity kind.
_EQH_NS = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
_EQL_NS = UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")
_POOL_NS = UUID("6ba7b813-9dad-11d1-80b4-00c04fd430c8")
_ZONE_NS = UUID("6ba7b814-9dad-11d1-80b4-00c04fd430c8")
_SWEEP_NS = UUID("6ba7b815-9dad-11d1-80b4-00c04fd430c8")


def equal_highs_id(
    symbol: str,
    timeframe: str,
    price: str,
    bar_indices: tuple[int, ...],
) -> UUID:
    bars = ",".join(str(i) for i in bar_indices)
    return uuid5(_EQH_NS, f"{symbol}:{timeframe}:{price}:{bars}")


def equal_lows_id(
    symbol: str,
    timeframe: str,
    price: str,
    bar_indices: tuple[int, ...],
) -> UUID:
    bars = ",".join(str(i) for i in bar_indices)
    return uuid5(_EQL_NS, f"{symbol}:{timeframe}:{price}:{bars}")


def pool_id(
    symbol: str,
    timeframe: str,
    side: str,
    price: str,
    first_bar: int,
    last_bar: int,
) -> UUID:
    return uuid5(
        _POOL_NS,
        f"{symbol}:{timeframe}:{side}:{price}:{first_bar}:{last_bar}",
    )


def zone_id(
    symbol: str,
    timeframe: str,
    side: str,
    low_price: str,
    high_price: str,
) -> UUID:
    return uuid5(
        _ZONE_NS,
        f"{symbol}:{timeframe}:{side}:{low_price}:{high_price}",
    )


def sweep_id(pool: UUID, bar_index: int) -> UUID:
    return uuid5(_SWEEP_NS, f"{pool}:{bar_index}")
