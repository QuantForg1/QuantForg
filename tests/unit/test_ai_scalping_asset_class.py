"""Asset-class multi-symbol gate helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    classify_volatility_band,
)
from app.domain.institutional_trading.ai_scalping.asset_class import (
    asset_class_for_symbol,
    broker_symbol_candidates,
    classify_atr_band_thresholds,
    resolve_spread_limits,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)


@pytest.mark.unit
def test_asset_classes() -> None:
    assert asset_class_for_symbol("XAUUSD") == "gold"
    assert asset_class_for_symbol("XAUUSD_I") == "gold"
    assert asset_class_for_symbol("EURUSD") == "fx"
    assert asset_class_for_symbol("EURUSD_I") == "fx"
    assert asset_class_for_symbol("USDJPY") == "fx"
    assert asset_class_for_symbol("NAS100") == "index"
    assert asset_class_for_symbol("NDXUSD") == "index"
    assert asset_class_for_symbol("SPXUSD") == "index"
    assert asset_class_for_symbol("DJIUSD") == "index"
    assert asset_class_for_symbol("BTCUSD") == "crypto"
    assert asset_class_for_symbol("LTCUSD") == "crypto"


@pytest.mark.unit
def test_index_and_crypto_not_fx_spread_ceiling() -> None:
    """Regression: NDXUSD/LTCUSD were misclassified as FX → reject 0.001."""
    idx_reject, _, _, _ = resolve_spread_limits(
        "NDXUSD",
        max_spread_reject=Decimal("1.50"),
        max_spread_for_full_score=Decimal("0.40"),
        max_spread_atr_pct=Decimal("15"),
    )
    assert idx_reject == Decimal("8.0")
    d_idx = assess_spread(Decimal("4.10"), symbol="NDXUSD")
    assert d_idx.reject is False

    cry_reject, _, _, _ = resolve_spread_limits(
        "LTCUSD",
        max_spread_reject=Decimal("1.50"),
        max_spread_for_full_score=Decimal("0.40"),
        max_spread_atr_pct=Decimal("15"),
    )
    assert cry_reject == Decimal("80")
    d_ltc = assess_spread(Decimal("0.35"), symbol="LTCUSD")
    assert d_ltc.reject is False


@pytest.mark.unit
def test_broker_candidates_include_weltrade_i_suffix() -> None:
    eurusd = broker_symbol_candidates("EURUSD")
    assert "EURUSD" in eurusd
    assert "EURUSD_I" in eurusd
    xau = broker_symbol_candidates("XAUUSD")
    assert "XAUUSD_I" in xau
    # Reverse: broker form still tries desk code
    assert "EURUSD" in broker_symbol_candidates("EURUSD_I")


@pytest.mark.unit
def test_gold_band_not_stuck_in_low_at_production_atr() -> None:
    # Live ATR% ≈ 0.118 must classify as normal under multi-symbol bands
    band, atr_pct = classify_volatility_band(
        Decimal("2.85"),
        Decimal("2405"),
        symbol="XAUUSD",
    )
    assert atr_pct is not None
    assert atr_pct == pytest.approx(Decimal("0.1185031185"), rel=Decimal("0.01"))
    assert band == "normal"


@pytest.mark.unit
def test_fx_spread_not_rejected_by_gold_atr_pct() -> None:
    # Prior bug: atr_cap ≈ 0 → every EURUSD tick rejected
    d = assess_spread(
        Decimal("0.00026"),
        atr=Decimal("0.00028"),
        symbol="EURUSD",
    )
    assert d.reject is False
    assert d.score > 0


@pytest.mark.unit
def test_jpy_spread_uses_jpy_pip_scale() -> None:
    d = assess_spread(
        Decimal("0.020"),
        atr=Decimal("0.125"),
        symbol="USDJPY",
    )
    assert d.reject is False


@pytest.mark.unit
def test_index_broker_candidates() -> None:
    assert "USTEC" in broker_symbol_candidates("NAS100")
    assert "DJ30" in broker_symbol_candidates("US30")
    assert "DE40" in broker_symbol_candidates("GER40")


@pytest.mark.unit
def test_spread_limits_fx() -> None:
    reject, full, atr_pct, floor = resolve_spread_limits(
        "EURUSD",
        max_spread_reject=Decimal("1.50"),
        max_spread_for_full_score=Decimal("0.40"),
        max_spread_atr_pct=Decimal("15"),
    )
    assert reject < Decimal("0.01")
    assert floor > 0
    assert atr_pct >= Decimal("50")
    low, high = classify_atr_band_thresholds(
        "EURUSD",
        gold_low=Decimal("0.40"),
        gold_high=Decimal("1.50"),
    )
    assert low < Decimal("0.10")
    assert high < Decimal("0.50")
