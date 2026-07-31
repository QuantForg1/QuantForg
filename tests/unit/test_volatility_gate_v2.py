"""Volatility Gate v2 — adaptive ATR floor unit + before/after replay."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
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
from app.domain.institutional_trading.ai_scalping.volatility_gate_v2 import (
    evaluate_volatility_gate_v1_compat,
    evaluate_volatility_gate_v2,
)
from app.domain.institutional_trading.decision_models import TradeDirection

# M15 ATR% bucket shares from VOLATILITY_GATE_CALIBRATION_REPORT (30d)
_M15_BUCKET_SHARES = {
    "0.08": 0.0257,  # <0.10 representative
    "0.125": 0.2718,  # 0.10-0.15
    "0.175": 0.3465,  # 0.15-0.20
    "0.25": 0.2906,  # 0.20-0.30
    "0.35": 0.0653,  # >0.30
}

# Historical non-micro winners ATR% (calibration)
_HIST_WINNER_ATR = [
    0.1604,
    0.1502,
    0.2056,
    0.171,
    0.171,
    0.171,
    0.171,
    0.171,
    0.3454,
    0.157,
]


def _low_thresholds() -> ResolvedThresholds:
    return ResolvedThresholds(
        band="low",
        quality=88,
        confidence=88,
        atr_pct=Decimal("0.17"),
    )


def _spread_ok(score: int = 100) -> SpreadAssessment:
    return SpreadAssessment(
        score=score,
        reject=False,
        confidence_penalty=0,
        reason="tight",
    )


def _direction_buy() -> DirectionDecision:
    return DirectionDecision(
        direction=TradeDirection.BUY,
        buy_score=85,
        sell_score=15,
        reasons=("test",),
        structure_score=85,
        factors={},
    )


def _strong_kwargs() -> dict:
    return {
        "trade_quality": 90,
        "confidence": 92,
        "structure_score": 85,
        "liquidity": 88,
        "momentum": 80,
        "mtf_alignment": 100,
        "session": assess_session("new_york"),
        "spread": _spread_ok(100),
        "thresholds": _low_thresholds(),
        "market_regime": "strong_trend",
        "pa_passed": True,
        "direction_clear": True,
    }


def _weak_kwargs() -> dict:
    return {
        "trade_quality": 82,
        "confidence": 82,
        "structure_score": 72,
        "liquidity": 62,
        "momentum": 66,
        "mtf_alignment": 55,
        "session": assess_session("tokyo"),
        "spread": _spread_ok(60),
        "thresholds": _low_thresholds(),
        "market_regime": "range",
        "pa_passed": True,
        "direction_clear": True,
    }


@pytest.mark.unit
def test_config_preserves_quality_confidence_floors() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version == "ai-scalping-v7.3.0"
    assert cfg.quality_baseline == "ai-scalping-v6.3.0"
    assert cfg.normal_vol.quality >= 80
    assert cfg.normal_vol.confidence >= 80
    assert cfg.low_vol.quality >= 80
    assert cfg.low_vol.confidence >= 80
    assert cfg.atr_compression_floor_pct == Decimal("0.20")
    assert cfg.atr_exceptional_floor_pct == Decimal("0.15")
    assert cfg.atr_hard_min_pct == Decimal("0.15")
    assert cfg.atr_exceptional_floor_pct >= cfg.atr_hard_min_pct
    assert cfg.atr_compression_floor_pct >= cfg.atr_exceptional_floor_pct


@pytest.mark.unit
def test_v1_compat_fixed_floor() -> None:
    assert evaluate_volatility_gate_v1_compat(
        atr_pct=Decimal("0.19"), band="low"
    ) is False
    assert evaluate_volatility_gate_v1_compat(
        atr_pct=Decimal("0.20"), band="low"
    ) is True
    assert evaluate_volatility_gate_v1_compat(
        atr_pct=Decimal("0.10"), band="normal"
    ) is True


@pytest.mark.unit
def test_weak_setup_still_rejects_below_standard_floor() -> None:
    d = evaluate_volatility_gate_v2(atr_pct=Decimal("0.17"), **_weak_kwargs())
    assert d.passed is False
    assert d.exceptional_eligible is False
    assert d.applied_floor_pct == Decimal("0.20")
    assert d.legacy_would_pass is False
    assert d.to_dict()["model"] == "volatility_gate_v2"


@pytest.mark.unit
def test_exceptional_setup_allows_evidence_band() -> None:
    d = evaluate_volatility_gate_v2(atr_pct=Decimal("0.17"), **_strong_kwargs())
    assert d.passed is True
    assert d.exceptional_eligible is True
    assert d.exceptional_used is True
    assert d.applied_floor_pct == Decimal("0.15")
    assert d.legacy_would_pass is False  # v1 would still block


@pytest.mark.unit
def test_hard_min_blocks_even_exceptional() -> None:
    # Live blocker ATR% ≈ 0.13 — still fail under v2
    d = evaluate_volatility_gate_v2(atr_pct=Decimal("0.13"), **_strong_kwargs())
    assert d.passed is False
    assert d.applied_floor_pct == Decimal("0.15")
    assert "hard minimum" in d.reason.lower() or "hard min" in d.reason.lower() or (
        "0.15" in d.reason
    )


@pytest.mark.unit
def test_standard_floor_unchanged_for_ge_020() -> None:
    weak = evaluate_volatility_gate_v2(atr_pct=Decimal("0.21"), **_weak_kwargs())
    strong = evaluate_volatility_gate_v2(atr_pct=Decimal("0.21"), **_strong_kwargs())
    assert weak.passed is True
    assert strong.passed is True
    assert weak.exceptional_used is False
    assert strong.exceptional_used is False


@pytest.mark.unit
def test_quality_gates_record_volatility_decision() -> None:
    gates = evaluate_quality_gates(
        direction=_direction_buy(),
        momentum=80,
        liquidity=88,
        structure_score=85,
        session=assess_session("london"),
        spread=_spread_ok(),
        thresholds=_low_thresholds(),
        confidence=92,
        trade_quality=90,
        expected_rr=Decimal("1.5"),
        atr_pct=Decimal("0.17"),
        mtf_alignment=100,
        market_regime="strong_trend",
    )
    assert gates.volatility_decision is not None
    assert gates.volatility_decision["model"] == "volatility_gate_v2"
    assert gates.checks["valid_volatility"] is True
    assert gates.passed is True


@pytest.mark.unit
def test_quality_gates_weak_atr_band_still_fail() -> None:
    gates = evaluate_quality_gates(
        direction=_direction_buy(),
        momentum=66,
        liquidity=62,
        structure_score=72,
        session=assess_session("tokyo"),
        spread=_spread_ok(60),
        thresholds=_low_thresholds(),
        confidence=82,
        trade_quality=82,
        expected_rr=Decimal("1.5"),
        atr_pct=Decimal("0.17"),
        mtf_alignment=55,
        market_regime="range",
    )
    assert gates.checks["valid_volatility"] is False
    assert any("compressed" in r.lower() or "Volatility" in r for r in gates.rejects)


@pytest.mark.unit
def test_before_after_replay_no_false_positive_increase() -> None:
    """Weak setups must not gain accepts; only exceptional strength may."""
    weak_new_accepts = 0
    strong_new_accepts = 0
    both_accept = 0
    both_reject = 0
    v1_only = 0

    for label, share in _M15_BUCKET_SHARES.items():
        atr = Decimal(label)
        v1 = evaluate_volatility_gate_v1_compat(atr_pct=atr, band="low")
        weak = evaluate_volatility_gate_v2(atr_pct=atr, **_weak_kwargs()).passed
        strong = evaluate_volatility_gate_v2(atr_pct=atr, **_strong_kwargs()).passed

        # Weight by market share for aggregate stats (unit-scale counts)
        w = share
        if v1 and weak and strong:
            both_accept += w
        elif (not v1) and (not weak) and (not strong):
            both_reject += w
        elif v1 and (not weak or not strong):
            v1_only += w
        if (not v1) and weak:
            weak_new_accepts += w
        if (not v1) and strong and not weak:
            strong_new_accepts += w

        # Hard invariant: weak never newly accepted vs v1
        if not v1:
            assert weak is False

    assert weak_new_accepts == 0
    # Evidence band 0.15-0.20 (~34.65%) newly available only for exceptional
    assert strong_new_accepts == pytest.approx(0.3465, abs=0.001)
    assert both_accept == pytest.approx(0.2906 + 0.0653, abs=0.001)


@pytest.mark.unit
def test_historical_winner_atr_replay() -> None:
    """Profitable ATR cluster: exceptional recovers 0.15-0.20; weak does not."""
    v1_pass = 0
    v2_weak_pass = 0
    v2_strong_pass = 0
    for atr_f in _HIST_WINNER_ATR:
        atr = Decimal(str(atr_f))
        if evaluate_volatility_gate_v1_compat(atr_pct=atr, band="low"):
            v1_pass += 1
        if evaluate_volatility_gate_v2(atr_pct=atr, **_weak_kwargs()).passed:
            v2_weak_pass += 1
        if evaluate_volatility_gate_v2(atr_pct=atr, **_strong_kwargs()).passed:
            v2_strong_pass += 1

    assert v1_pass == 2  # 0.2056 and 0.3454 only
    assert v2_weak_pass == v1_pass  # no weak false positives
    assert v2_strong_pass == 10  # all evidence winners recoverable if strong
    assert v2_strong_pass > v1_pass
