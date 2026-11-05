"""DIRECTION_NONE reject text must expose LTF edge — observability only."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
)
from app.domain.institutional_trading.decision_models import TradeDirection


def _gates(direction: DirectionDecision):
    thresholds = resolve_adaptive_thresholds(
        atr=Decimal("5"), mid=Decimal("2400"), config=DEFAULT_AI_SCALPING_CONFIG
    )
    return evaluate_quality_gates(
        direction=direction,
        momentum=70,
        liquidity=70,
        structure_score=80,
        session=assess_session("london"),
        spread=SpreadAssessment(
            score=100, reject=False, confidence_penalty=0, reason="tight"
        ),
        atr_pct=Decimal("0.8"),
        confidence=90,
        trade_quality=80,
        expected_rr=Decimal("0.5"),
        thresholds=thresholds,
        config=DEFAULT_AI_SCALPING_CONFIG,
        pa_confluence=None,
    )


@pytest.mark.unit
def test_direction_none_reject_includes_ltf_conflict_detail() -> None:
    gates = _gates(
        DirectionDecision(
            direction=TradeDirection.NONE,
            buy_score=40,
            sell_score=42,
            reasons=("CONFLICT",),
            structure_score=85,
            factors={},
            ltf_buy_score=28,
            ltf_sell_score=30,
            directional_edge=2,
            edge_margin=5,
        )
    )
    assert gates.checks["clear_direction"] is False
    assert any("CONFLICT" in r and "LTF BUY 28" in r for r in gates.hard_rejects)
    assert any("edge=2/5" in r for r in gates.hard_rejects)
    assert any(
        r.startswith("No clear BUY/SELL edge (balanced scores → reject")
        for r in gates.hard_rejects
    )


@pytest.mark.unit
def test_direction_none_reject_marks_no_ltf_edge() -> None:
    gates = _gates(
        DirectionDecision(
            direction=TradeDirection.NONE,
            buy_score=8,
            sell_score=8,
            reasons=("No M1/M5 directional edge",),
            structure_score=20,
            factors={},
            ltf_buy_score=0,
            ltf_sell_score=0,
            directional_edge=0,
            edge_margin=5,
        )
    )
    assert any("NO_LTF_EDGE" in r for r in gates.hard_rejects)
