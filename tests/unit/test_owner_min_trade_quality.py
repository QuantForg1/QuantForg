"""Owner hard floor: robot entries need AI trade quality >= 80 (2026-10-24)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading import owner_live_limits as limits
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

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _gates(trade_quality: int):
    thresholds = resolve_adaptive_thresholds(
        atr=Decimal("5"), mid=Decimal("2400"), config=DEFAULT_AI_SCALPING_CONFIG
    )
    return evaluate_quality_gates(
        direction=DirectionDecision(
            direction=TradeDirection.BUY,
            buy_score=80,
            sell_score=20,
            reasons=("test",),
            structure_score=80,
            factors={},
        ),
        momentum=70,
        liquidity=70,
        structure_score=80,
        session=assess_session("london"),
        spread=SpreadAssessment(
            score=100, reject=False, confidence_penalty=0, reason="tight"
        ),
        atr_pct=Decimal("0.8"),
        confidence=90,
        trade_quality=trade_quality,
        expected_rr=Decimal("2.0"),
        thresholds=thresholds,
        config=DEFAULT_AI_SCALPING_CONFIG,
        pa_confluence=None,
    )


def _floor_rejects(gates) -> list[str]:
    return [r for r in gates.hard_rejects if r.startswith("OWNER_MIN_TRADE_QUALITY")]


def test_floor_is_80() -> None:
    assert limits.OWNER_MIN_TRADE_QUALITY == 80


@pytest.mark.parametrize("quality", [0, 60, 75, 79])
def test_quality_below_80_is_a_hard_reject(quality: int) -> None:
    gates = _gates(quality)
    assert gates.checks["owner_min_trade_quality"] is False
    assert _floor_rejects(gates) == [
        f"OWNER_MIN_TRADE_QUALITY: trade quality {quality} < 80"
    ]
    assert gates.passed is False
    assert any(r.startswith("OWNER_MIN_TRADE_QUALITY") for r in gates.rejects)


@pytest.mark.parametrize("quality", [80, 85, 100])
def test_quality_80_and_above_passes_the_floor(quality: int) -> None:
    gates = _gates(quality)
    assert gates.checks["owner_min_trade_quality"] is True
    assert _floor_rejects(gates) == []


# ---------------------------------------------------------------- live scorer
def _score(total: int):
    from app.domain.institutional_trading.ai_scalping.scoring import (
        score_scalping_setup,
    )
    from app.domain.market_structure.enums import TrendDirection
    from tests.unit.test_xauusd_sniper_v2_lifecycle import _bos, _fvg, _snap, _struct

    snap = _snap(
        macro=TrendDirection.UP,
        primary=TrendDirection.UNKNOWN,
        entry=TrendDirection.DOWN,
        execution=TrendDirection.DOWN,
        m1=_struct(bos=[_bos("DOWN")]),
        m5=_struct(bos=[_bos("DOWN")]),
        fvgs=[_fvg(side="BEARISH", high="2612", low="2608")],
    )
    snap.trade_quality.total = total
    snap.trade_quality.components = {"momentum": 52, "liquidity": 40, "volume": 40}
    snap.entry_atr = None
    return score_scalping_setup(
        snap,
        atr=Decimal("4.00"),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        symbol="XAUUSD_i",
    )


def test_live_scorer_rejects_a_robot_setup_below_the_floor() -> None:
    out = _score(63)
    assert out.trade_quality == 63
    assert out.reject is True
    assert "OWNER_MIN_TRADE_QUALITY: trade quality 63 < 80" in out.reject_reasons


def test_live_scorer_does_not_apply_the_floor_at_85() -> None:
    out = _score(85)
    assert out.trade_quality == 85
    assert not any(r.startswith("OWNER_MIN_TRADE_QUALITY") for r in out.reject_reasons)
