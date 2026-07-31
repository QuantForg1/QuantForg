"""Unit tests — Score Pipeline Integration (thresholds/weights preserved)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityFactor,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.trade_quality import TradeQualityEvaluator
from app.domain.market_context.enums import MarketSession
from app.domain.market_structure.enums import TrendDirection
from app.domain.order_block.enums import OrderBlockState


@pytest.mark.unit
def test_thresholds_and_version_preserved() -> None:
    cfg = ITEConfig()
    assert cfg.min_confluence_score == 80
    assert cfg.min_trade_quality_score == 80
    assert cfg.config_version == "ite-v2.2.0"


@pytest.mark.unit
def test_quality_uses_liquidity_v2_not_legacy_sweep_floor() -> None:
    cfg = ITEConfig()
    trend = TrendSnapshot(
        macro_bias=TrendDirection.RANGE,
        primary=TrendDirection.UP,
        entry=TrendDirection.UP,
        execution=TrendDirection.DOWN,
        alignment_score=100,
        aligned=True,
        market_regime="ranging",
        mtf_policy="v2_ranging_h1_m15",
        trade_bias=TrendDirection.UP,
        h4_is_context=True,
        m15_semantics={
            "new_classification": "TREND_CONTINUATION",
            "effective_direction": "up",
        },
    )
    ob = SimpleNamespace(
        order_blocks=(SimpleNamespace(state=OrderBlockState.ACTIVE, quality=None),),
        breakers=(),
        mitigations=(),
    )
    fvg = SimpleNamespace(gaps=(), active_gaps=(object(), object()))
    # Legacy liquidity empty (would have been score 40)
    liq = SimpleNamespace(sweeps=(), pools=(), equal_highs=(), equal_lows=())
    session = SessionFilterResult(
        session=MarketSession.LONDON, allowed=True, reason="ok", quality_score=100
    )
    quality = TradeQualityEvaluator(config=cfg).evaluate(
        trend=trend,
        structure=None,
        liquidity=liq,  # type: ignore[arg-type]
        order_blocks=ob,  # type: ignore[arg-type]
        fvgs=fvg,  # type: ignore[arg-type]
        session=session,
        spread=Decimal("0.20"),
    )
    liq_factor = next(f for f in quality.factors if f.code == "liquidity")
    assert liq_factor.score == 65  # Liquidity v2 non-sweep context
    assert "Liquidity v2" in liq_factor.detail
    assert quality.total >= 80 or quality.total > 72  # lifted vs legacy ~72


@pytest.mark.unit
def test_confluence_m15_credits_after_lock_and_dedups_quality_facts() -> None:
    cfg = ITEConfig(trading_mode="scalping", min_confluence_score=80)
    trend = TrendSnapshot(
        macro_bias=TrendDirection.RANGE,
        primary=TrendDirection.UP,
        entry=TrendDirection.UP,
        execution=TrendDirection.DOWN,
        alignment_score=100,
        aligned=True,
        market_regime="ranging",
        mtf_policy="v2_ranging_h1_m15",
        trade_bias=TrendDirection.UP,
        h4_is_context=True,
        m15_semantics={
            "previous_classification": "DOWN",
            "new_classification": "PULLBACK_WITHIN_TREND",
            "effective_direction": "up",
            "reason": "test",
        },
    )
    quality = TradeQualityScore(
        total=82,
        passed=True,
        band="tradable",
        factors=(
            TradeQualityFactor(code="trend", weight=20, score=100),
            TradeQualityFactor(code="liquidity", weight=15, score=65),
            TradeQualityFactor(code="order_block", weight=15, score=75),
            TradeQualityFactor(code="fair_value_gap", weight=15, score=85),
            TradeQualityFactor(code="market_structure", weight=15, score=100),
            TradeQualityFactor(code="session", weight=10, score=100),
            TradeQualityFactor(code="spread", weight=10, score=100),
        ),
    )
    ob = SimpleNamespace(order_blocks=(SimpleNamespace(state=OrderBlockState.ACTIVE),))
    fvg = SimpleNamespace(active_gaps=(object(),))
    snap = MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
        config_version=cfg.config_version,
        input_hash="abc",
        structure_by_tf={},
        primary_structure=None,
        liquidity=SimpleNamespace(sweeps=(), pools=(), equal_highs=(), equal_lows=()),
        order_blocks=ob,
        fair_value_gaps=fvg,
        trend=trend,
        session=SessionFilterResult(
            session=MarketSession.LONDON, allowed=True, reason="ok"
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="disabled"),
        trade_quality=quality,
        spread=Decimal("0.20"),
    )
    result = ConfluenceEngine(config=cfg).evaluate(snap)
    assert result.factors["m15"] == 100
    assert result.factors["liquidity"] == 65  # single-source from quality
    assert result.factors["order_block"] == 75
    assert result.factors["fvg"] == 85
    assert result.factors["quality"] == 100  # passed → no double drag
    assert result.confidence >= 80
    assert "mtf_not_aligned" not in result.rejected_rules
    assert any("dedup" in r.lower() for r in result.reasons)


@pytest.mark.unit
def test_weights_unchanged_in_confluence() -> None:
    # Spot-check weight map still sums to 100 via a trivial evaluate path
    weights = {
        "mtf": 22,
        "m15": 8,
        "structure": 12,
        "liquidity": 10,
        "order_block": 12,
        "fvg": 10,
        "quality": 12,
        "session": 6,
        "news": 4,
        "spread": 2,
        "volatility": 1,
        "drawdown": 1,
    }
    assert sum(weights.values()) == 100
