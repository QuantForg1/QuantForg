"""Unit tests — AI Scalping Mode (adaptive thresholds, sizing, MTF, guards)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    apply_thresholds_to_ite,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.regime import classify_scalping_regime
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.sizing import calculate_scalping_lots
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.market_data.timeframe import Timeframe


@pytest.mark.unit
def test_scalping_ite_config_drops_h4_requirement() -> None:
    cfg = scalping_ite_config()
    assert cfg.is_scalping()
    assert cfg.macro_bias_tf is Timeframe.H1
    assert cfg.primary_structure_tf is Timeframe.M15
    assert cfg.entry_confirmation_tf is Timeframe.M5
    assert cfg.execution_management_tf is Timeframe.M1
    assert Timeframe.H4 not in cfg.analysis_timeframes()
    assert cfg.max_open_trades == 3


@pytest.mark.unit
def test_adaptive_thresholds_by_volatility() -> None:
    mid = Decimal("4000")
    high = resolve_adaptive_thresholds(Decimal("80"), mid)  # 2% ATR
    assert high.band == "high"
    assert high.quality == DEFAULT_AI_SCALPING_CONFIG.high_vol.quality
    assert high.confidence == DEFAULT_AI_SCALPING_CONFIG.high_vol.confidence

    normal = resolve_adaptive_thresholds(Decimal("20"), mid)  # 0.5%
    assert normal.band == "normal"

    low = resolve_adaptive_thresholds(Decimal("8"), mid)  # 0.2%
    assert low.band == "low"
    assert low.quality == DEFAULT_AI_SCALPING_CONFIG.low_vol.quality

    applied = apply_thresholds_to_ite(DEFAULT_ITE_CONFIG, high)
    assert applied.min_trade_quality_score == high.quality
    assert applied.min_confluence_score == high.confidence
    # Original defaults unchanged
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80


@pytest.mark.unit
def test_dynamic_lot_sizing_respects_broker_step() -> None:
    sized = calculate_scalping_lots(
        equity=Decimal("1000"),
        stop_distance=Decimal("5"),
        risk_pct=Decimal("1.0"),
    )
    assert sized.valid
    assert sized.lots >= Decimal("0.01")
    # Must be multiple of 0.01
    assert (sized.lots * 100) % 1 == 0

    blocked = calculate_scalping_lots(
        equity=Decimal("10"),
        stop_distance=Decimal("50"),
        risk_pct=Decimal("0.1"),
    )
    assert blocked.valid is False or blocked.lots == Decimal("0")


@pytest.mark.unit
def test_spread_soft_penalty_hard_reject_only_at_ceiling() -> None:
    soft = assess_spread(Decimal("1.00"))
    assert soft.reject is False
    assert soft.confidence_penalty > 0

    hard = assess_spread(Decimal("3.00"))
    assert hard.reject is True


@pytest.mark.unit
def test_session_aggression_london_ny() -> None:
    london = assess_session("london")
    assert london.aggressive is True
    assert london.stars == 5
    tokyo = assess_session("tokyo")
    assert tokyo.aggressive is False
    assert tokyo.confidence_penalty > 0


@pytest.mark.unit
def test_add_trade_requires_probability_improvement() -> None:
    first = may_add_scalping_trade(
        open_positions=0,
        max_open=3,
        new_confidence=70,
        best_open_confidence=None,
        new_direction="BUY",
    )
    assert first.allow

    blocked = may_add_scalping_trade(
        open_positions=1,
        max_open=3,
        new_confidence=70,
        best_open_confidence=70,
        new_direction="BUY",
        require_improvement=True,
        min_confidence_delta=3,
    )
    assert blocked.allow is False

    improved = may_add_scalping_trade(
        open_positions=1,
        max_open=3,
        new_confidence=75,
        best_open_confidence=70,
        new_direction="BUY",
        require_improvement=True,
        min_confidence_delta=3,
    )
    assert improved.allow


@pytest.mark.unit
def test_regime_classification() -> None:
    trending = classify_scalping_regime(alignment_score=80, bos=1)
    assert trending.regime == "trending"
    reversal = classify_scalping_regime(alignment_score=40, choch=1, sweep_count=1)
    assert reversal.regime == "reversal"


@pytest.mark.unit
def test_default_swing_ite_unchanged() -> None:
    assert DEFAULT_ITE_CONFIG.trading_mode == "swing"
    assert DEFAULT_ITE_CONFIG.macro_bias_tf is Timeframe.H4
    assert DEFAULT_ITE_CONFIG.max_open_trades == 1
    assert ITEConfig().is_scalping() is False
