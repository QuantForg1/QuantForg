"""Deterministic input fingerprinting for reproducible analysis."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime

from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe


def _candle_digest(candles: Sequence[Candle]) -> str:
    parts: list[str] = []
    for c in candles:
        parts.append(
            f"{c.open_time.isoformat()}|{c.open}|{c.high}|{c.low}|{c.close}|{c.volume}"
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_input_hash(
    *,
    symbol: str,
    as_of: datetime,
    config_version: str,
    bars_by_tf: Mapping[Timeframe, Sequence[Candle]],
    spread: str | None = None,
) -> str:
    """Stable hash of symbol + config + bar series (+ optional spread)."""
    chunks = [
        symbol.strip().upper(),
        config_version,
        as_of.astimezone().isoformat() if as_of.tzinfo else as_of.isoformat(),
        f"spread={spread or ''}",
    ]
    for tf in sorted(bars_by_tf.keys(), key=lambda t: t.value):
        series = bars_by_tf[tf]
        chunks.append(f"{tf.value}:{len(series)}:{_candle_digest(series)}")
    raw = "|".join(chunks)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
