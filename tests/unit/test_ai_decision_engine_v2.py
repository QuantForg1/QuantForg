"""Unit tests — AI Decision Engine v2 (MTF regime + liquidity; no threshold cuts)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.liquidity_v2 import (
    evaluate_liquidity_v1_legacy,
    evaluate_liquidity_v2,
)
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.mtf_v2 import (
    evaluate_mtf_v1_legacy,
    evaluate_mtf_v2,
)
from app.domain.institutional_trading.trend_engine import TrendEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.order_block.enums import OrderBlockState
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
def test_mtf_v2_ranging_h4_not_veto_when_lower_tfs_lock() -> None:
    v2 = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.UP,
        scalping=True,
    )
    assert v2.regime == "ranging"
    assert v2.h4_is_context is True
    assert v2.aligned is True
    assert v2.bias is TrendDirection.UP
    assert v2.contributions.get("h4", 0) == 0

    v1 = evaluate_mtf_v1_legacy(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.UP,
        scalping=True,
    )
    # Legacy confluence keyed on raw H4 → permanent veto
    assert v1.aligned is False


@pytest.mark.unit
def test_mtf_v2_ranging_still_requires_m15_agreement() -> None:
    v2 = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.DOWN,
        m5=TrendDirection.UP,
        scalping=True,
    )
    assert v2.aligned is False


@pytest.mark.unit
def test_mtf_v2_ranging_h1_m15_lock_does_not_require_m5() -> None:
    v2 = evaluate_mtf_v2(
        h4=TrendDirection.RANGE,
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.DOWN,
        scalping=True,
    )
    assert v2.aligned is True
    assert v2.policy == "v2_ranging_h1_m15"


@pytest.mark.unit
def test_mtf_v2_trending_requires_h4_h1_m15() -> None:
    ok = evaluate_mtf_v2(
        h4=TrendDirection.UP,
        h1=TrendDirection.UP,
        m15=TrendDirection.UP,
        m5=TrendDirection.RANGE,
        scalping=False,
    )
    assert ok.regime == "trending"
    assert ok.aligned is True

    bad = evaluate_mtf_v2(
        h4=TrendDirection.UP,
        h1=TrendDirection.UP,
        m15=TrendDirection.DOWN,
        m5=TrendDirection.UP,
        scalping=False,
    )
    assert bad.aligned is False


@pytest.mark.unit
def test_trend_engine_uses_v2_ranging_policy() -> None:
    cfg = ITEConfig(trading_mode="scalping")
    by_tf = {
        Timeframe.H4: _struct(Timeframe.H4, TrendDirection.RANGE),
        Timeframe.H1: _struct(Timeframe.H1, TrendDirection.UP),
        Timeframe.M15: _struct(Timeframe.M15, TrendDirection.UP),
        Timeframe.M5: _struct(Timeframe.M5, TrendDirection.UP),
    }
    trend = TrendEngine(config=cfg).analyze(by_tf)
    assert trend.market_regime == "ranging"
    assert trend.h4_is_context is True
    assert trend.aligned is True
    assert trend.effective_bias is TrendDirection.UP


@pytest.mark.unit
def test_liquidity_v2_accepts_validated_ob_without_sweeps() -> None:
    ob_block = SimpleNamespace(
        state=OrderBlockState.VALIDATED,
        quality=SimpleNamespace(displacement_ratio=Decimal("2.0")),
    )
    snapshot = SimpleNamespace(
        liquidity=SimpleNamespace(
            sweeps=(), pools=(), equal_highs=(), equal_lows=()
        ),
        order_blocks=SimpleNamespace(order_blocks=(ob_block,), mitigations=()),
        fair_value_gaps=SimpleNamespace(active_gaps=()),
    )
    v1 = evaluate_liquidity_v1_legacy(snapshot)
    v2 = evaluate_liquidity_v2(snapshot)
    assert v1.rejected is True
    assert v1.score == 20
    assert v2.rejected is False
    assert v2.score == 65  # no inflation above prior non-sweep ceiling
    assert "validated_order_block" in v2.sources
    assert "displacement" in v2.sources


@pytest.mark.unit
def test_confluence_v2_clears_mtf_and_liquidity_false_negatives() -> None:
    cfg = ITEConfig(trading_mode="scalping", min_confluence_score=80)
    trend = TrendSnapshot(
        macro_bias=TrendDirection.RANGE,
        primary=TrendDirection.UP,
        entry=TrendDirection.UP,
        execution=TrendDirection.UP,
        alignment_score=100,
        aligned=True,
        market_regime="ranging",
        mtf_policy="v2_ranging",
        trade_bias=TrendDirection.UP,
        mtf_contributions={"h4": 0, "h1": 50, "m15": 50, "m5_timing_bonus": 0},
        h4_is_context=True,
        why="test",
    )
    ob_block = SimpleNamespace(state=OrderBlockState.ACTIVE, quality=None)
    fvg = SimpleNamespace(active_gaps=(object(),))
    snap = MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
        config_version=cfg.config_version,
        input_hash="abc",
        structure_by_tf={},
        primary_structure=None,
        liquidity=SimpleNamespace(
            sweeps=(), pools=(), equal_highs=(), equal_lows=()
        ),
        order_blocks=SimpleNamespace(order_blocks=(ob_block,), mitigations=()),
        fair_value_gaps=fvg,
        trend=trend,
        session=SessionFilterResult(
            session=MarketSession.LONDON, allowed=True, reason="ok"
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="disabled"),
        trade_quality=TradeQualityScore(total=85, passed=True, band="tradable"),
        spread=Decimal("0.20"),
    )
    result = ConfluenceEngine(config=cfg).evaluate(snap)
    assert "mtf_not_aligned" not in result.rejected_rules
    assert "no_liquidity_context" not in result.rejected_rules
    assert result.factors["liquidity"] == 65
    assert result.direction.value == "BUY"


@pytest.mark.unit
def test_thresholds_unchanged() -> None:
    cfg = ITEConfig()
    assert cfg.min_confluence_score == 80
    assert cfg.min_trade_quality_score == 80
    assert cfg.config_version == "ite-v2.2.0"
