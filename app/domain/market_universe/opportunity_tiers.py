"""Research/display opportunity bands.

These labels never change the live Opportunity 70 gate.
Missing scores stay UNKNOWN — never coerced to 0 or LOW.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    FROZEN_OPPORTUNITY_THRESHOLD,
    OPPORTUNITY_TIER_EXTREME,
    OPPORTUNITY_TIER_HIGH,
    OPPORTUNITY_TIER_LOW,
    OPPORTUNITY_TIER_MODERATE,
    OPPORTUNITY_TIER_VERY_HIGH,
    UNKNOWN,
)


def research_opportunity_tier(opportunity: Any) -> str:
    """Map a numeric Opportunity onto a research display band."""
    if opportunity in (None, "", UNKNOWN):
        return UNKNOWN
    try:
        n = int(float(opportunity))
    except (TypeError, ValueError):
        return UNKNOWN
    if n >= 90:
        return OPPORTUNITY_TIER_EXTREME
    if n >= 80:
        return OPPORTUNITY_TIER_VERY_HIGH
    if n >= FROZEN_OPPORTUNITY_THRESHOLD:
        return OPPORTUNITY_TIER_HIGH
    if n >= 60:
        return OPPORTUNITY_TIER_MODERATE
    if n >= 0:
        return OPPORTUNITY_TIER_LOW
    return UNKNOWN


def opportunity_band_label(opportunity: Any) -> str:
    """Bucket label for analytics grouping. UNKNOWN if unmeasured."""
    if opportunity in (None, "", UNKNOWN):
        return UNKNOWN
    try:
        n = int(float(opportunity))
    except (TypeError, ValueError):
        return UNKNOWN
    if n >= 90:
        return "90-100"
    if n >= 80:
        return "80-89"
    if n >= 70:
        return "70-79"
    if n >= 60:
        return "60-69"
    return "<60"
