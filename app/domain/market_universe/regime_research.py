"""Research-only regime labels. Never a live trading filter."""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import RESEARCH_REGIME_LABELS, UNKNOWN

_ALIASES: dict[str, str] = {
    "TREND": "TREND",
    "TRENDING": "TREND",
    "BULL_TREND": "TREND",
    "BEAR_TREND": "TREND",
    "RANGE": "RANGE",
    "RANGING": "RANGE",
    "MEAN_REVERT": "RANGE",
    "MEAN_REVERSION": "RANGE",
    "BREAKOUT": "BREAKOUT",
    "EXPANSION": "BREAKOUT",
    "REVERSAL": "REVERSAL",
    "EXHAUSTION": "REVERSAL",
    "HIGH_VOLATILITY": "HIGH_VOLATILITY",
    "HIGH_VOL": "HIGH_VOLATILITY",
    "VOLATILE": "HIGH_VOLATILITY",
    "LOW_VOLATILITY": "LOW_VOLATILITY",
    "LOW_VOL": "LOW_VOLATILITY",
    "QUIET": "LOW_VOLATILITY",
    "NEWS_VOLATILITY": "NEWS_VOLATILITY",
    "NEWS": "NEWS_VOLATILITY",
    "EVENT": "NEWS_VOLATILITY",
}


def normalize_research_regime(value: Any) -> str:
    """Map existing regime strings onto the research vocabulary.

    Unknown / empty stays UNKNOWN. Does not invent a regime from missing data.
    """
    if value in (None, "", UNKNOWN):
        return UNKNOWN
    raw = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    if raw in RESEARCH_REGIME_LABELS:
        return raw
    mapped = _ALIASES.get(raw)
    if mapped:
        return mapped
    for key, label in _ALIASES.items():
        if key in raw:
            return label
    return UNKNOWN
