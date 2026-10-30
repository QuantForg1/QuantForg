"""Gold opportunity quality + $50 min-lot risk — no invented confidence."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.setup_scanner import (
    scan_setup_families,
)
from app.domain.trading.gold_opportunity_quality import (
    assess_gold_opportunity,
    min_lot_fits_equity_risk,
    min_lot_risk_dollars,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_assess_passes_when_aligned_and_spread_ok() -> None:
    out = assess_gold_opportunity(
        mtf_aligned=True,
        spread=Decimal("0.40"),
        session_allowed=True,
        stop_loss_present=True,
        risk_reward_ok=True,
        min_lot_fits_risk=True,
    )
    assert out.tradable is True
    assert out.to_dict()["confidence"] is None
    assert out.skip_reasons == ()


def test_assess_skips_mtf_conflict_and_stale() -> None:
    out = assess_gold_opportunity(
        mtf_conflict=True,
        data_fresh=False,
        missing_candles=True,
    )
    assert out.tradable is False
    assert any("Multi-timeframe" in r for r in out.skip_reasons)
    assert any("Stale" in r for r in out.skip_reasons)
    assert any("Missing candles" in r for r in out.skip_reasons)


def test_assess_skips_false_breakout_in_range() -> None:
    out = assess_gold_opportunity(
        range_bound=True,
        false_breakout_risk=True,
    )
    assert out.tradable is False
    assert any("false-breakout" in r.lower() for r in out.skip_reasons)


def test_fifty_dollar_min_lot_exceeds_conservative_risk() -> None:
    """At ~$50 equity, typical Gold stop makes min lot violate 1% risk."""
    equity = Decimal("50")
    stop = Decimal("18")  # ATR-style Gold stop distance
    risk_pct = Decimal("1.00")
    dollar = min_lot_risk_dollars(stop_distance=stop)
    assert dollar == Decimal("18.00")  # 0.01 * 100 * 18
    assert (
        min_lot_fits_equity_risk(
            equity=equity,
            risk_pct=risk_pct,
            stop_distance=stop,
        )
        is False
    )
    out = assess_gold_opportunity(min_lot_fits_risk=False)
    assert out.tradable is False
    assert any("min lot" in r.lower() for r in out.skip_reasons)


def test_setup_scanner_vetoes_on_mtf_conflict() -> None:
    result = scan_setup_families(
        alignment=90,
        bos=1,
        momentum=70,
        ema=70,
        volume=80,
        buy_score=80,
        sell_score=20,
        atr_band="high",
        mtf_conflict=True,
    )
    assert result.best is None
    assert any("Multi-timeframe" in r for r in result.reasons)


def test_setup_scanner_drops_breakout_on_false_breakout_risk() -> None:
    result = scan_setup_families(
        alignment=80,
        bos=1,
        momentum=70,
        ema=70,
        volume=90,
        buy_score=80,
        sell_score=20,
        atr_band="high",
        false_breakout_risk=True,
        range_bound=True,
    )
    # Hard skip from quality gate (range + false-breakout)
    assert result.best is None
