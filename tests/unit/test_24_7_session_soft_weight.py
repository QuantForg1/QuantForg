"""24/7 session soft-weighting — no session-only hard blocks for named windows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.sizing import calculate_scalping_lots
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.models import (
    SessionFilterResult,
    TrendSnapshot,
)
from app.domain.institutional_trading.session_filter import SessionFilter
from app.domain.institutional_trading.session_policy import (
    TRADABLE_SESSION_NAMES,
    TRADABLE_SESSIONS_24_7,
    quality_score_for_session,
    risk_multiplier_for_session,
)
from app.domain.institutional_trading.trade_quality import TradeQualityEvaluator
from app.domain.market_context.enums import MarketSession
from app.domain.market_structure.enums import TrendDirection


@pytest.mark.unit
class TestTwentyFourSevenSessions:
    def test_defaults_include_all_named_sessions(self) -> None:
        assert set(DEFAULT_ITE_CONFIG.allowed_sessions) == set(TRADABLE_SESSIONS_24_7)
        assert set(DEFAULT_AI_SCALPING_CONFIG.allowed_sessions) == set(
            TRADABLE_SESSION_NAMES
        )
        assert DEFAULT_AI_SCALPING_CONFIG.require_session_quality is False

    def test_all_named_sessions_allowed_with_soft_weights(self) -> None:
        filt = SessionFilter(config=ITEConfig())
        for session in TRADABLE_SESSIONS_24_7:
            result = filt.evaluate(
                as_of=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
                session=session,
            )
            assert result.allowed is True, session
            assert result.stars >= 2
            assert 0 < result.risk_multiplier <= Decimal("1")
            assert result.quality_score == quality_score_for_session(session)

    def test_off_hours_still_blocked(self) -> None:
        result = SessionFilter(config=ITEConfig()).evaluate(
            as_of=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),  # Saturday
        )
        assert result.session is MarketSession.OFF_HOURS
        assert result.allowed is False

    def test_tokyo_soft_weights_confidence_and_risk(self) -> None:
        tokyo = assess_session("tokyo")
        london = assess_session("london")
        assert tokyo.aggressive is False
        assert tokyo.confidence_penalty > 0
        assert tokyo.risk_multiplier < london.risk_multiplier
        assert tokyo.quality_score < london.quality_score

    def test_session_quality_gate_does_not_hard_reject_tokyo(self) -> None:
        from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
            resolve_adaptive_thresholds,
        )
        from app.domain.institutional_trading.ai_scalping.direction import (
            DirectionDecision,
        )
        from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
            SpreadAssessment,
        )
        from app.domain.institutional_trading.decision_models import TradeDirection

        sess = assess_session("tokyo")
        assert sess.stars < DEFAULT_AI_SCALPING_CONFIG.min_session_stars
        thresholds = resolve_adaptive_thresholds(
            atr=Decimal("5"),
            mid=Decimal("2400"),
            config=DEFAULT_AI_SCALPING_CONFIG,
        )
        direction = DirectionDecision(
            direction=TradeDirection.BUY,
            buy_score=80,
            sell_score=20,
            reasons=("test",),
            structure_score=80,
            factors={},
        )
        spread = SpreadAssessment(
            score=100,
            reject=False,
            confidence_penalty=0,
            reason="tight",
        )
        gates = evaluate_quality_gates(
            direction=direction,
            momentum=70,
            liquidity=70,
            structure_score=80,
            session=sess,
            spread=spread,
            atr_pct=Decimal("0.8"),
            confidence=thresholds.confidence + 5,
            trade_quality=thresholds.quality + 5,
            expected_rr=Decimal("1.5"),
            thresholds=thresholds,
            config=DEFAULT_AI_SCALPING_CONFIG,
            pa_confluence=None,
        )
        # Soft: session_quality check may be False (stars < min) but must not reject
        assert gates.checks.get("session_quality") is False
        assert not any("Session quality" in r for r in gates.rejects)

    def test_sizing_reduces_risk_for_weak_session_never_increases(self) -> None:
        base = calculate_scalping_lots(
            equity=Decimal("10000"),
            stop_distance=Decimal("5"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            session_risk_multiplier=Decimal("1.00"),
        )
        weak = calculate_scalping_lots(
            equity=Decimal("10000"),
            stop_distance=Decimal("5"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            session_risk_multiplier=risk_multiplier_for_session("tokyo"),
        )
        assert base.valid and weak.valid
        assert weak.lots <= base.lots
        assert "session_risk_scale" in weak.method

    def test_trade_quality_uses_soft_session_score(self) -> None:
        trend = TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.UP,
            entry=TrendDirection.UP,
            execution=TrendDirection.UP,
            alignment_score=90,
            aligned=True,
            why="aligned",
        )
        tokyo = SessionFilterResult(
            session=MarketSession.TOKYO,
            allowed=True,
            reason="tokyo soft",
            quality_score=55,
            risk_multiplier=Decimal("0.70"),
            stars=2,
        )
        london = SessionFilterResult(
            session=MarketSession.LONDON,
            allowed=True,
            reason="london",
            quality_score=100,
            risk_multiplier=Decimal("1.00"),
            stars=5,
        )
        ev = TradeQualityEvaluator(config=ITEConfig())
        tq = ev.evaluate(
            trend=trend,
            structure=None,
            liquidity=None,
            order_blocks=None,
            fvgs=None,
            session=tokyo,
            spread=Decimal("0.30"),
        )
        lq = ev.evaluate(
            trend=trend,
            structure=None,
            liquidity=None,
            order_blocks=None,
            fvgs=None,
            session=london,
            spread=Decimal("0.30"),
        )
        tokyo_factor = next(f for f in tq.factors if f.code == "session")
        london_factor = next(f for f in lq.factors if f.code == "session")
        assert tokyo_factor.score == 55
        assert london_factor.score == 100
        assert tq.total <= lq.total
