"""Unit tests — M15 Trend Semantics v2 (no threshold cuts)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.m15_semantics_v2 import (
    M15SemanticLabel,
    classify_m15_semantics,
    overlay_m15_semantics_on_structure,
)
from app.domain.institutional_trading.mtf_v2 import evaluate_mtf_v2
from app.domain.institutional_trading.trend_engine import TrendEngine
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode


def _struct(tf: Timeframe, direction: TrendDirection) -> StructureSnapshot:
    code = SymbolCode(value="XAUUSD")
    as_of = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    return StructureSnapshot(
        symbol_code=code,
        timeframe=tf,
        as_of=as_of,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=tf,
            direction=direction,
            as_of=as_of,
            last_structure_role=StructureRole.UNKNOWN,
            swing_count=0,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )


@pytest.mark.unit
def test_pullback_within_trend_does_not_become_down() -> None:
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.DOWN,
        bos_direction=TrendDirection.UP,
        has_valid_bos=True,
        has_valid_ob=True,
        has_valid_fvg=True,
    )
    assert sem.new_classification is M15SemanticLabel.PULLBACK_WITHIN_TREND
    assert sem.effective_direction is TrendDirection.UP
    assert sem.previous_classification == "DOWN"
    assert sem.confirmed_reversal is False


@pytest.mark.unit
def test_consolidation_aligns_with_h1() -> None:
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.RANGE,
        bos_direction=TrendDirection.UP,
        has_valid_bos=True,
        has_valid_ob=False,
        has_valid_fvg=False,
    )
    assert sem.new_classification is M15SemanticLabel.CONSOLIDATION
    assert sem.effective_direction is TrendDirection.UP


@pytest.mark.unit
def test_trend_continuation_requires_bos_ob_fvg() -> None:
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.RANGE,
        bos_direction=TrendDirection.UP,
        has_valid_bos=True,
        has_valid_ob=True,
        has_valid_fvg=True,
    )
    assert sem.new_classification is M15SemanticLabel.TREND_CONTINUATION
    assert sem.effective_direction is TrendDirection.UP


@pytest.mark.unit
def test_true_regime_reversal_keeps_down() -> None:
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.DOWN,
        bos_direction=TrendDirection.DOWN,
        choch_opposes_bias=True,
        has_valid_bos=True,
        has_valid_ob=True,
        has_valid_fvg=True,
    )
    assert sem.new_classification is M15SemanticLabel.TRUE_REGIME_REVERSAL
    assert sem.effective_direction is TrendDirection.DOWN
    assert sem.confirmed_reversal is True


@pytest.mark.unit
def test_mtf_ranging_h1_m15_lock_ignores_m5_conflict() -> None:
    """M5 must not redefine H1; H1+M15 lock is sufficient."""
    v2 = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.DOWN,
        scalping=True,
    )
    assert v2.policy == "v2_ranging_h1_m15"
    assert v2.aligned is True
    assert v2.bias is TrendDirection.UP


@pytest.mark.unit
def test_mtf_ranging_still_requires_m15_agreement() -> None:
    v2 = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.DOWN,
        m5=TrendDirection.UP,
        scalping=True,
    )
    assert v2.aligned is False


@pytest.mark.unit
def test_semantics_plus_lock_recovers_pullback_cycle() -> None:
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.DOWN,
        bos_direction=TrendDirection.UP,
        has_valid_bos=True,
        has_valid_ob=True,
        has_valid_fvg=True,
    )
    after = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=sem.effective_direction,
        m5=TrendDirection.DOWN,
        scalping=True,
    )
    assert after.aligned is True


@pytest.mark.unit
def test_trend_engine_applies_semantics_and_ignores_m5() -> None:
    cfg = ITEConfig(trading_mode="scalping")
    by_tf = {
        Timeframe.H4: _struct(Timeframe.H4, TrendDirection.RANGE),
        Timeframe.H1: _struct(Timeframe.H1, TrendDirection.UP),
        Timeframe.M15: _struct(Timeframe.M15, TrendDirection.DOWN),
        Timeframe.M5: _struct(Timeframe.M5, TrendDirection.DOWN),
    }
    # Without OB/FVG/BOS on empty snaps → consolidation/pullback still aligns
    trend = TrendEngine(config=cfg).analyze(by_tf)
    assert trend.m15_semantics.get("new_classification") in {
        "PULLBACK_WITHIN_TREND",
        "CONSOLIDATION",
        "TREND_CONTINUATION",
    }
    assert trend.entry is TrendDirection.UP  # rewritten
    assert trend.execution is TrendDirection.DOWN  # untouched
    assert trend.aligned is True
    assert trend.mtf_policy == "v2_ranging_h1_m15"


@pytest.mark.unit
def test_overlay_does_not_rewrite_on_confirmed_reversal() -> None:
    # Build minimal snaps; classify directly for reversal path
    sem = classify_m15_semantics(
        structural_bias=TrendDirection.UP,
        m15_raw=TrendDirection.DOWN,
        bos_direction=TrendDirection.DOWN,
        choch_opposes_bias=True,
        has_valid_bos=True,
    )
    assert sem.effective_direction is TrendDirection.DOWN


@pytest.mark.unit
def test_thresholds_unchanged_v21() -> None:
    cfg = ITEConfig()
    assert cfg.min_confluence_score == 80
    assert cfg.min_trade_quality_score == 80
    assert cfg.config_version == "ite-v2.1.0"
