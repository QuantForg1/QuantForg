"""Scalping MTF labels versus the clock timeframes that produced Trend 0.

The quality trend component reads alignment_score. On SCALPING_V1 the slots
named H4/H1/M15/M5 inside evaluate_mtf_v2 are filled with H1/M15/M5/M1.
The score is unchanged by naming the clock timeframes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from app.domain.institutional_trading.ai_scalping.config import scalping_ite_config
from app.domain.institutional_trading.models import TrendSnapshot
from app.domain.institutional_trading.trend_engine import TrendEngine
from app.domain.market_data.closed_bars import closed_analysis_bars
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.market_structure.trend_classifier import TrendClassifier
from app.domain.value_objects.identity import SymbolCode
from tests.unit.market_structure_fakes import make_candle

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _dir(direction: TrendDirection) -> SimpleNamespace:
    return SimpleNamespace(trend=SimpleNamespace(direction=direction))


def _analyze(**directions: TrendDirection) -> TrendSnapshot:
    cfg = scalping_ite_config()
    mapped = cast(
        "dict[Timeframe, StructureSnapshot]",
        {
            Timeframe.H1: _dir(directions["h1"]),
            Timeframe.M15: _dir(directions["m15"]),
            Timeframe.M5: _dir(directions["m5"]),
            Timeframe.M1: _dir(directions["m1"]),
        },
    )
    return TrendEngine(config=cfg).analyze(mapped, apply_m15_semantics=False)


def test_production_range_inputs_score_zero_and_name_m1_not_m5() -> None:
    """00:34 UTC roles: H1 range, M15 range, M5 range, M1 up. Score stays 0."""
    trend = _analyze(
        h1=TrendDirection.RANGE,
        m15=TrendDirection.RANGE,
        m5=TrendDirection.RANGE,
        m1=TrendDirection.UP,
    )
    assert trend.alignment_score == 0
    assert trend.aligned is False
    assert trend.market_regime == "ranging"
    assert "clock H1=range M15=range M5=range M1=up" in trend.why
    assert trend.frames == {
        "H1": "range",
        "M15": "range",
        "M5": "range",
        "M1": "up",
    }


def test_m5_up_does_not_create_a_higher_timeframe_trend() -> None:
    trend = _analyze(
        h1=TrendDirection.RANGE,
        m15=TrendDirection.RANGE,
        m5=TrendDirection.UP,
        m1=TrendDirection.UP,
    )
    assert trend.alignment_score == 0
    assert trend.aligned is False
    assert trend.trade_bias is TrendDirection.UNKNOWN


def test_agreed_bullish_stack_aligns() -> None:
    trend = _analyze(
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.UP,
        m1=TrendDirection.UP,
    )
    assert trend.alignment_score == 100
    assert trend.aligned is True
    assert trend.trade_bias is TrendDirection.UP
    assert "clock H1=up M15=up M5=up M1=up" in trend.why


def test_agreed_bearish_stack_aligns() -> None:
    trend = _analyze(
        h1=TrendDirection.DOWN,
        m15=TrendDirection.DOWN,
        m5=TrendDirection.DOWN,
        m1=TrendDirection.DOWN,
    )
    assert trend.alignment_score == 100
    assert trend.aligned is True
    assert trend.trade_bias is TrendDirection.DOWN


def test_h1_up_m15_down_conflicts_and_does_not_align() -> None:
    trend = _analyze(
        h1=TrendDirection.UP,
        m15=TrendDirection.DOWN,
        m5=TrendDirection.UP,
        m1=TrendDirection.UP,
    )
    assert trend.aligned is False
    assert trend.alignment_score < 55
    assert trend.trade_bias is TrendDirection.UP


def test_missing_timeframe_is_unknown_not_a_direction() -> None:
    cfg = scalping_ite_config()
    trend = TrendEngine(config=cfg).analyze(
        cast("dict[Timeframe, StructureSnapshot]", {}),
        apply_m15_semantics=False,
    )
    assert trend.macro_bias is TrendDirection.UNKNOWN
    assert trend.primary is TrendDirection.UNKNOWN
    assert trend.alignment_score == 0
    assert trend.aligned is False


def test_equal_swing_roles_classify_range() -> None:
    from app.domain.market_structure.enums import StructureRole

    symbol = SymbolCode.of("XAUUSD")
    moment = datetime(2026, 11, 6, tzinfo=UTC)
    nodes = [
        SimpleNamespace(role=role)
        for role in (
            StructureRole.HIGHER_HIGH,
            StructureRole.LOWER_LOW,
            StructureRole.LOWER_HIGH,
            StructureRole.HIGHER_LOW,
        )
    ]
    classified = TrendClassifier().classify(
        nodes,  # type: ignore[arg-type]
        symbol_code=symbol,
        timeframe=Timeframe.H1,
        as_of=moment,
    )
    assert classified.direction is TrendDirection.RANGE


def test_bos_requires_a_close_not_a_wick() -> None:
    high = make_candle(index=1, high="10", low="8", close="9", open_="8.5")
    wick = make_candle(index=3, high="11", low="8.5", close="9.5", open_="9")
    close_break = make_candle(index=4, high="12", low="9", close="10.5", open_="9.5")
    from app.domain.market_structure.enums import SwingKind
    from app.domain.market_structure.models import SwingPoint

    swing = SwingPoint.create(
        symbol_code=high.symbol_code,
        timeframe=high.timeframe,
        kind=SwingKind.HIGH,
        price=high.high,
        bar_index=1,
        timestamp=high.close_time,
        strength=1,
    )
    held = StructureAnalyzer().detect_breaks(
        swings=(swing,),
        candles=(high, wick),
        trend=TrendDirection.UP,
    )
    assert held.breaks_of_structure == ()
    broken = StructureAnalyzer().detect_breaks(
        swings=(swing,),
        candles=(high, close_break),
        trend=TrendDirection.UP,
    )
    assert len(broken.breaks_of_structure) == 1


def test_forming_bar_is_excluded_from_structure_input() -> None:
    closed = make_candle(index=0, high="10", low="9", close="9.5")
    forming = make_candle(index=1, high="12", low="9", close="11.5")
    as_of = closed.close_time
    kept = closed_analysis_bars((closed, forming), as_of=as_of, timeframe=Timeframe.M15)
    assert kept == [closed]


def test_unconfirmed_edge_cannot_be_a_swing() -> None:
    candles = [
        make_candle(index=i, high=str(10 + (i % 3)), low=str(8 + (i % 3)))
        for i in range(6)
    ]
    swings = SwingDetector().detect(candles, left=2, right=2)
    assert all(swing.bar_index <= len(candles) - 3 for swing in swings)
