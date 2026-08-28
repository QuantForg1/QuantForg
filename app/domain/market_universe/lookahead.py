"""Lookahead detection for research features. Never uses future bars."""

from __future__ import annotations

from typing import Any

FUTURE_FIELD_MARKERS = (
    "future_",
    "next_candle",
    "next_bar",
    "lookahead",
    "future_bos",
    "future_choch",
    "future_fvg",
    "future_pnl",
    "future_spread",
)


def detect_lookahead_fields(row: dict[str, Any] | None) -> list[str]:
    """Return keys that would leak future information into a research feature."""
    leaked: list[str] = []
    for key in dict(row or {}):
        low = str(key).lower()
        if any(marker in low for marker in FUTURE_FIELD_MARKERS):
            leaked.append(str(key))
    return leaked
