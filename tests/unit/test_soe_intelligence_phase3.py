"""Phase 3 LIVE SOE intelligence — regime fit, MTF/LTF, NY, chase gates."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyEvaluation,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    ORCHESTRATION_VERSION,
    orchestrate_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.soe_intelligence import (
    evidence_intelligence_reason,
    filter_candidates_by_ltf_session,
    is_ny_quality_session,
    ltf_htf_disagreement_reason,
    ny_solo_bars,
    regime_suitability_boost,
)


def _ev(
    sid: str,
    *,
    passed: bool = True,
    direction: str = "BUY",
    quality: int = 88,
    confidence: int = 86,
) -> StrategyEvaluation:
    return StrategyEvaluation(
        strategy_id=sid,  # type: ignore[arg-type]
        name=sid,
        symbol="XAUUSD",
        direction=direction if passed else "NONE",
        passed=passed,
        quality=quality,
        confidence=confidence,
        explanation="t",
        reject_reason=None if passed else "fail",
        filters={},
        score_components={},
    )


def _pack(
    *,
    winner: str,
    quality: int = 88,
    others_pass: bool = False,
) -> tuple[StrategyEvaluation, ...]:
    ids = (
        "smc_scalping",
        "trend_continuation",
        "breakout_scalping",
        "range_mean_reversion",
        "momentum_scalping",
    )
    return tuple(
        _ev(
            sid,
            passed=(sid == winner) or others_pass,
            quality=quality if sid == winner else (quality - 2 if others_pass else 20),
            confidence=quality - 2 if sid == winner else 20,
        )
        for sid in ids
    )


@pytest.mark.unit
def test_orchestration_version_phase3() -> None:
    assert ORCHESTRATION_VERSION.startswith("soe-v1.5")


@pytest.mark.unit
def test_regime_suitability_prefers_specialist_not_hardcoded_tc() -> None:
    range_score = {"market_regime": "range"}
    breakout_score = {"market_regime": "breakout"}
    assert regime_suitability_boost("range_mean_reversion", range_score) > 0
    assert regime_suitability_boost("trend_continuation", range_score) < 0
    assert regime_suitability_boost("breakout_scalping", breakout_score) > (
        regime_suitability_boost("trend_continuation", breakout_score)
    )
    # Weak trend: SMC ranked above TC (anti-monoculture soft bias).
    assert regime_suitability_boost("smc_scalping", {"market_regime": "weak_trend"}) > (
        regime_suitability_boost("trend_continuation", {"market_regime": "weak_trend"})
    )


@pytest.mark.unit
def test_ltf_disagreement_blocks_trend_continuation_only() -> None:
    score = {
        "direction": "BUY",
        "market_regime": "strong_trend",
        "mtf_alignment": 72,
        "factors": {"m5_entry": 0, "m5_bos": 20, "m15_structure": 0, "mtf": 72},
    }
    assert ltf_htf_disagreement_reason("trend_continuation", score)
    assert ltf_htf_disagreement_reason("momentum_scalping", score)
    assert ltf_htf_disagreement_reason("smc_scalping", score) is None
    assert ltf_htf_disagreement_reason("breakout_scalping", score) is None


@pytest.mark.unit
def test_ltf_absent_keys_do_not_invent_disagreement() -> None:
    score = {"direction": "BUY", "market_regime": "strong_trend", "mtf_alignment": 75}
    assert ltf_htf_disagreement_reason("trend_continuation", score) is None


@pytest.mark.unit
def test_soe_demotes_tc_when_ltf_range_allows_smc() -> None:
    # TC quality higher, but LTF disagreement demotes it; SMC remains.
    evals = (
        _ev("smc_scalping", quality=84, confidence=82),
        _ev("trend_continuation", quality=92, confidence=90),
        _ev("breakout_scalping", passed=False, quality=20),
        _ev("range_mean_reversion", passed=False, quality=20),
        _ev("momentum_scalping", passed=False, quality=20),
    )
    score = {
        "direction": "BUY",
        "market_regime": "weak_trend",
        "mtf_alignment": 72,
        "net_reward_risk": 1.2,
        "factors": {
            "m5_entry": 0,
            "m5_bos": 20,
            "m15_structure": 0,
            "mtf": 72,
            "bos": 80,
            "momentum": 70,
            "volatility": 70,
        },
    }
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is False
    assert verdict.selected is not None
    assert verdict.selected.strategy_id == "smc_scalping"
    gated = any(
        "ltf_session_gate:trend_continuation" in r for r in verdict.reasons
    )
    rejected_ltf = any(
        "HTF/LTF" in (rj.reason or "") or "M5" in (rj.reason or "")
        for rj in verdict.rejected
    )
    assert gated or rejected_ltf


@pytest.mark.unit
def test_ny_session_raises_solo_bar() -> None:
    assert is_ny_quality_session({"market_session": "new_york"})
    assert ny_solo_bars({"market_session": "london"}) is None
    bars = ny_solo_bars({"market_session": "new_york"})
    assert bars is not None
    assert bars[0] >= 86

    # Hold-only advisory isolates NY solo bar from score-factor soft-clear.
    from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
        AdvisoryVote,
    )

    pack = _pack(winner="smc_scalping", quality=83)
    hold_only = (
        AdvisoryVote(
            "neutral", "Neutral", "HOLD", 40, "isolated", "score_factor_advisory"
        ),
    )
    verdict = orchestrate_strategies(
        pack,
        score={
            "direction": "BUY",
            "market_regime": "strong_trend",
            "market_session": "new_york",
            "mtf_alignment": 75,
            "net_reward_risk": 1.5,
            "factors": {"bos": 80, "momentum": 70, "volatility": 70, "mtf": 75},
        },
        advisory_votes=hold_only,
    )
    assert verdict.prefer_no_trade is True
    ny_or_solo = any(
        "ny_session" in r.lower() or "solo" in r.lower() for r in verdict.reasons
    )
    assert ny_or_solo


@pytest.mark.unit
def test_chase_setup_prefers_no_trade() -> None:
    reason = evidence_intelligence_reason(
        {"sniper_entry": {"setup_state": "CHASING"}, "direction": "BUY"}
    )
    assert reason is not None
    assert "CHASING" in reason

    pack = _pack(winner="smc_scalping", quality=90)
    verdict = orchestrate_strategies(
        pack,
        score={
            "direction": "BUY",
            "market_regime": "strong_trend",
            "mtf_alignment": 80,
            "net_reward_risk": 2.0,
            "sniper_entry": {"setup_state": "CHASING"},
            "factors": {"bos": 80, "momentum": 70, "volatility": 70, "mtf": 80},
        },
    )
    assert verdict.prefer_no_trade is True


@pytest.mark.unit
def test_buy_exhaustion_prefers_no_trade() -> None:
    reason = evidence_intelligence_reason(
        {
            "direction": "BUY",
            "momentum": 82,
            "structure_score": 40,
            "factors": {"timing_retest": 20, "momentum": 82, "bos": 40},
        }
    )
    assert reason is not None
    assert "exhaustion" in reason.lower()


@pytest.mark.unit
def test_filter_candidates_keeps_non_trendish() -> None:
    cands = [
        _ev("trend_continuation", quality=90),
        _ev("smc_scalping", quality=85),
        _ev("breakout_scalping", quality=84),
    ]
    score = {
        "direction": "BUY",
        "mtf_alignment": 70,
        "factors": {"m5_entry": 0, "m5_bos": 20, "m15_structure": 0},
    }
    kept, demoted = filter_candidates_by_ltf_session(cands, score)
    ids = {e.strategy_id for e in kept}
    assert "smc_scalping" in ids
    assert "breakout_scalping" in ids
    assert "trend_continuation" not in ids
    assert any(e.strategy_id == "trend_continuation" for e, _ in demoted)


@pytest.mark.unit
def test_regime_rank_selects_breakout_over_tc_when_both_pass() -> None:
    evals = (
        _ev("smc_scalping", passed=False, quality=20),
        _ev("trend_continuation", quality=85, confidence=84),
        _ev("breakout_scalping", quality=85, confidence=84),
        _ev("range_mean_reversion", passed=False, quality=20),
        _ev("momentum_scalping", passed=False, quality=20),
    )
    score = {
        "direction": "BUY",
        "market_regime": "breakout",
        "mtf_alignment": 78,
        "net_reward_risk": 1.8,
        "factors": {
            "m5_entry": 80,
            "m5_bos": 85,
            "m15_structure": 80,
            "bos": 85,
            "momentum": 75,
            "volatility": 80,
            "mtf": 78,
        },
    }
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is False
    assert verdict.selected is not None
    assert verdict.selected.strategy_id == "breakout_scalping"
