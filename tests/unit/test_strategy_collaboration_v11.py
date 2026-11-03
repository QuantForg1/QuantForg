"""SOE v1.1 — advisory collaboration, cost gate, eligibility registry."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
    AdvisoryVote,
    collect_score_factor_advisory_votes,
    summarize_advisory_agreement,
)
from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.live_eligibility import (
    eligibility_snapshot,
    live_executable_ids,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    ORCHESTRATION_VERSION,
    orchestrate_strategies,
)


def _base_score(**overrides):
    row = {
        "symbol": "XAUUSD",
        "reject": False,
        "direction": "SELL",
        "trade_quality": 80,
        "ai_confidence": 78,
        "structure_score": 72,
        "momentum": 70,
        "liquidity": 70,
        "mtf_alignment": 75,
        "spread_score": 70,
        "spread": 0.25,
        "expected_rr": 1.6,
        "market_regime": "strong_trend",
        "setup_family": "bos_continuation",
        "thresholds": {"quality": 74, "confidence": 71, "band": "normal"},
        "factors": {
            "bos": 85,
            "choch": 20,
            "order_block": 80,
            "fvg": 70,
            "momentum": 70,
            "volume": 75,
            "volatility": 70,
            "atr_expansion": 70,
            "ema": 70,
            "trend_strength": 75,
            "pa_confluence": 60,
            "liquidity_sweep": 70,
            "mtf": 75,
            "spread": 70,
        },
    }
    row.update(overrides)
    return row


@pytest.mark.unit
def test_soe_version_is_v11() -> None:
    assert ORCHESTRATION_VERSION == "soe-v1.4.0"


@pytest.mark.unit
def test_eligibility_five_live_executable() -> None:
    ids = live_executable_ids()
    assert len(ids) == 5
    assert "smc_scalping" in ids
    snap = eligibility_snapshot()
    assert snap["auto_authorize_live"] is False
    assert any(r["tier"] == "analysis_advisory" for r in snap["strategies"])
    assert any(r["tier"] == "forbidden" for r in snap["strategies"])


@pytest.mark.unit
def test_advisory_votes_participate_without_oms_authority() -> None:
    votes = collect_score_factor_advisory_votes(_base_score())
    assert len(votes) >= 5
    assert all(v.may_select_for_oms is False for v in votes)
    assert all(v.source == "score_factor_advisory" for v in votes)
    summary = summarize_advisory_agreement(live_direction="SELL", votes=votes)
    assert summary["advisory_total"] == len(votes)
    assert "agree_count" in summary


@pytest.mark.unit
def test_collaboration_attaches_advisory_to_verdict() -> None:
    # Clear preferred-RR solo raise with net RR at preferred floor.
    score = _base_score(expected_rr=2.0, net_reward_risk=2.0)
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is False
    assert verdict.selected is not None
    assert len(verdict.advisory_votes) >= 5
    assert verdict.collaboration.get("oms_winner_allowed_from_advisory") is False
    assert verdict.to_dict()["live_auto_authorize"] is False


@pytest.mark.unit
def test_strong_advisory_disagreement_prefers_no_trade() -> None:
    score = _base_score()
    # Inject strong opposite advisory votes against a mid-quality solo passer.
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    mid = StrategyEvaluation(
        strategy_id="smc_scalping",
        name="SMC",
        symbol="XAUUSD",
        direction="BUY",
        passed=True,
        quality=80,
        confidence=78,
        explanation="mid",
        reject_reason=None,
        filters={},
        score_components={},
    )
    failed = [
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="NONE",
            passed=False,
            quality=20,
            confidence=20,
            explanation="x",
            reject_reason="x",
            filters={},
            score_components={},
        )
        for sid in (
            "trend_continuation",
            "breakout_scalping",
            "range_mean_reversion",
            "momentum_scalping",
        )
    ]
    # Phase-6: strong disagreement requires real engines (not score-factor proxies).
    disagree = (
        AdvisoryVote("rsi", "RSI", "SELL", 80, "disagree", "institutional_alpha"),
        AdvisoryVote("macd", "MACD", "SELL", 82, "disagree", "strategy_engine_plugin"),
    )
    verdict = orchestrate_strategies(
        (mid, *failed), advisory_votes=disagree, score=score
    )
    assert verdict.prefer_no_trade is True
    assert verdict.decision == "NO_TRADE"
    assert any("disagree" in r.lower() for r in verdict.reasons)


@pytest.mark.unit
def test_elevated_spread_weak_rr_prefers_no_trade() -> None:
    score = _base_score(spread=1.2, expected_rr=1.0)
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is True
    assert any(
        "spread" in r.lower() or "reward:risk" in r.lower() for r in verdict.reasons
    )


@pytest.mark.unit
def test_net_rr_below_owner_floor_prefers_no_trade() -> None:
    score = _base_score(expected_rr=1.2, spread=0.25)
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is True
    assert any("reward:risk" in r.lower() for r in verdict.reasons)


@pytest.mark.unit
def test_stale_setup_prefers_no_trade() -> None:
    score = _base_score(setup_age_seconds=180, expected_rr=1.8)
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is True
    assert any(
        "freshness" in r.lower() or "stale" in r.lower() for r in verdict.reasons
    )


@pytest.mark.unit
def test_false_breakout_evidence_prefers_no_trade() -> None:
    score = _base_score(
        expected_rr=1.8,
        structure_score=80,
        factors={
            "bos": 85,
            "volatility": 30,
            "atr_expansion": 30,
            "volume": 30,
            "momentum": 60,
            "mtf": 75,
            "liquidity_sweep": 70,
            "pa_confluence": 60,
            "ema": 70,
            "trend_strength": 70,
            "choch": 20,
            "order_block": 80,
            "fvg": 70,
            "spread": 70,
        },
    )
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is True
    assert any("false-breakout" in r.lower() for r in verdict.reasons)
