"""Probability Center RR quality must respect owner sub-1.0 geometry."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.operations.probability_selector import (
    _rr_quality,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.mark.parametrize(
    ("rr", "lo", "hi"),
    [
        (0.20, 38, 42),  # floor → ~40
        (0.35, 68, 72),  # mid → ~70
        (0.50, 98, 100),  # preferred → 100
        (0.40, 78, 82),  # common LIVE geometry
    ],
)
def test_owner_rr_maps_into_useful_quality_band(rr: float, lo: int, hi: int) -> None:
    q = _rr_quality(rr)
    assert q is not None
    assert lo <= q <= hi, (rr, q)


def test_legacy_sub_one_rr_no_longer_collapses_to_teens() -> None:
    # Old map: 40 + (0.40 - 1.0) * 40 = 16 — crushed opportunity_score.
    assert (_rr_quality(0.40) or 0) >= 70
