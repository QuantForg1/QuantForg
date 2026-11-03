"""Strategy Orchestration Engine — selectivity, influence, conflict, gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.strategies.backtest_gate import (
    evaluate_backtest_gate,
)
from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
    evaluate_strategy,
)
from app.domain.institutional_trading.ai_scalping.strategies.monitoring import (
    build_strategy_performance_monitor,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    MIN_SOLO_QUALITY,
    catalog_participation_policy,
    orchestrate_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    MOMENTUM_SCALPING,
    SMC_SCALPING,
)
from app.domain.institutional_trading.ai_scalping.strategies.select import (
    attach_strategies_to_scores,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
)
from app.domain.institutional_trading.ai_scalping.strategies.validation_status import (
    classify_strategy_health,
    influence_weight_for_strategy,
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
def test_momentum_floor_is_enforced() -> None:
    """Regression: min_momentum on StrategyDefinition must actually filter."""
    score = _base_score(
        momentum=50,
        factors={
            **_base_score()["factors"],
            "momentum": 50,
            "trend_strength": 50,
        },
    )
    ev = evaluate_strategy(score, MOMENTUM_SCALPING)
    assert ev.passed is False
    assert "Momentum" in (ev.reject_reason or "")


@pytest.mark.unit
def test_soe_selects_with_confluence_on_strong_setup() -> None:
    # Pass score so supportive advisory can clear cluster-solo selectivity.
    # Effective confluence counts thesis clusters (trend pack = 1), not raw passers.
    score = _base_score(net_reward_risk=2.2, expected_rr=2.2)
    evals = evaluate_all_strategies(score)
    verdict = orchestrate_strategies(evals, score=score)
    assert verdict.prefer_no_trade is False
    assert verdict.selected is not None
    assert verdict.decision in {"BUY", "SELL"}
    assert verdict.confluence_count >= 1
    assert verdict.selected.strategy_id in {
        "smc_scalping",
        "trend_continuation",
        "breakout_scalping",
        "momentum_scalping",
    }
    assert any("SOE selected" in r for r in verdict.reasons)


@pytest.mark.unit
def test_opportunity_enrich_preserves_soe_veto() -> None:
    from app.domain.institutional_trading.ai_scalping.opportunity_ranking import (
        enrich_scores_with_opportunity,
    )

    rows = enrich_scores_with_opportunity(
        [
            {
                **_base_score(),
                "soe_prefer_no_trade": True,
                "soe_blocks_selection": True,
                "strategy_id": "smc_scalping",
                "reject": False,
            }
        ]
    )
    assert rows[0]["opportunity_eligible"] is False
    assert rows[0]["strategy_id"] is None


@pytest.mark.unit
def test_correlated_trend_pack_is_one_confluence_cluster() -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )
    from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
        _effective_confluence_count,
    )

    pack = [
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="BUY",
            passed=True,
            quality=88,
            confidence=86,
            explanation="x",
            reject_reason=None,
            filters={},
            score_components={},
        )
        for sid in (
            "smc_scalping",
            "trend_continuation",
            "breakout_scalping",
            "momentum_scalping",
        )
    ]
    assert _effective_confluence_count(pack) == 1


@pytest.mark.unit
def test_soe_prefers_no_trade_on_weak_solo() -> None:
    """Only SMC-like weak quality → solo bar rejects (prefer no trade)."""
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    weak = StrategyEvaluation(
        strategy_id="smc_scalping",
        name="SMC Scalping",
        symbol="XAUUSD",
        direction="BUY",
        passed=True,
        quality=MIN_SOLO_QUALITY - 5,
        confidence=70,
        explanation="weak solo",
        reject_reason=None,
        filters={"ok": True},
        score_components={},
        live_rank_boost=0.0,
    )
    # Force other strategies failed
    failed = [
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="NONE",
            passed=False,
            quality=40,
            confidence=40,
            explanation="fail",
            reject_reason="fail",
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
    verdict = orchestrate_strategies((weak, *failed))
    assert verdict.prefer_no_trade is True
    assert verdict.selected is None
    assert verdict.decision == "NO_TRADE"


@pytest.mark.unit
def test_soe_direction_conflict_prefers_no_trade() -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    a = StrategyEvaluation(
        strategy_id="smc_scalping",
        name="SMC",
        symbol="XAUUSD",
        direction="BUY",
        passed=True,
        quality=90,
        confidence=90,
        explanation="buy",
        reject_reason=None,
        filters={},
        score_components={},
    )
    b = StrategyEvaluation(
        strategy_id="trend_continuation",
        name="Trend",
        symbol="XAUUSD",
        direction="SELL",
        passed=True,
        quality=91,
        confidence=91,
        explanation="sell",
        reject_reason=None,
        filters={},
        score_components={},
    )
    others = [
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="NONE",
            passed=False,
            quality=10,
            confidence=10,
            explanation="x",
            reject_reason="x",
            filters={},
            score_components={},
        )
        for sid in ("breakout_scalping", "range_mean_reversion", "momentum_scalping")
    ]
    verdict = orchestrate_strategies((a, b, *others))
    assert verdict.conflicting is True
    assert verdict.prefer_no_trade is True
    assert verdict.selected is None


@pytest.mark.unit
def test_deteriorating_strategy_influence_veto(tmp_path: Path) -> None:
    book = StrategyStatsBook(_path=tmp_path / "stats.json")
    for _ in range(5):
        book.record_closed("smc_scalping", win=True, pnl=2.0)
    for _ in range(8):
        book.record_closed("smc_scalping", win=False, pnl=-5.0)
    snap = book.snapshot()
    health = classify_strategy_health(
        next(r for r in snap["strategies"] if r["strategy_id"] == "smc_scalping")
    )
    assert health["status"] == "deteriorating"
    assert (
        influence_weight_for_strategy(strategy_id="smc_scalping", health_row=health)
        == 0.0
    )

    evals = evaluate_all_strategies(_base_score())
    verdict = orchestrate_strategies(evals, stats_snapshot=snap)
    # SMC may be vetoed; another healthy/insufficient strategy can still win,
    # or SOE may prefer no trade if remaining fail selectivity.
    if verdict.selected is not None:
        assert verdict.selected.strategy_id != "smc_scalping"


@pytest.mark.unit
def test_attach_marks_soe_prefer_no_trade() -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    weak_pack = tuple(
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="BUY" if sid == "smc_scalping" else "NONE",
            passed=sid == "smc_scalping",
            quality=70 if sid == "smc_scalping" else 20,
            confidence=60 if sid == "smc_scalping" else 20,
            explanation="x",
            reject_reason=None if sid == "smc_scalping" else "fail",
            filters={},
            score_components={},
        )
        for sid in (
            "smc_scalping",
            "trend_continuation",
            "breakout_scalping",
            "range_mean_reversion",
            "momentum_scalping",
        )
    )
    scored, global_best, winners = attach_strategies_to_scores(
        [_base_score()],
        evaluations_by_symbol={"XAUUSD": weak_pack},
    )
    assert global_best is None
    assert winners == []
    assert scored[0].get("soe_prefer_no_trade") is True
    assert scored[0].get("opportunity_eligible") is False
    assert scored[0].get("strategy_id") is None


@pytest.mark.unit
def test_backtest_gate_fail_closed_on_missing_metrics() -> None:
    out = evaluate_backtest_gate({}, strategy_id="smc_scalping")
    assert out["passed"] is False
    assert out["live_auto_authorize"] is False


@pytest.mark.unit
def test_backtest_gate_pass_still_not_auto_live() -> None:
    out = evaluate_backtest_gate(
        {
            "closed_trades": 40,
            "profit_factor": 1.4,
            "expectancy": 0.5,
            "max_drawdown_pct": 8.0,
            "win_rate": 55.0,
            "oos_passed": True,
            "walk_forward_passed": True,
        },
        strategy_id="trend_continuation",
    )
    assert out["passed"] is True
    assert out["live_auto_authorize"] is False


@pytest.mark.unit
def test_monitor_and_catalog_policy(tmp_path: Path) -> None:
    book = StrategyStatsBook(_path=tmp_path / "mon.json")
    book.record_evaluation("smc_scalping", passed=True)
    mon = build_strategy_performance_monitor(book)
    assert mon["live_execution_authorization"]["auto_authorize_live"] is False
    assert len(mon["strategies"]) == 5
    policy = catalog_participation_policy()
    assert "smc_scalping" in policy["live_executable_profiles"]
    assert "grid" in policy["never_live_from_catalog"]


@pytest.mark.unit
def test_smc_baseline_still_evaluates() -> None:
    ev = evaluate_strategy(_base_score(), SMC_SCALPING)
    assert ev.passed is True


@pytest.mark.unit
def test_weak_mtf_alignment_prefers_no_trade() -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    pack = tuple(
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="BUY" if sid == "smc_scalping" else "NONE",
            passed=sid == "smc_scalping",
            quality=90 if sid == "smc_scalping" else 20,
            confidence=88 if sid == "smc_scalping" else 20,
            explanation="x",
            reject_reason=None if sid == "smc_scalping" else "fail",
            filters={},
            score_components={},
        )
        for sid in (
            "smc_scalping",
            "trend_continuation",
            "breakout_scalping",
            "range_mean_reversion",
            "momentum_scalping",
        )
    )
    verdict = orchestrate_strategies(
        pack, score=_base_score(mtf_alignment=40, net_reward_risk=2.2)
    )
    assert verdict.prefer_no_trade is True
    assert any("multi-timeframe" in r.lower() for r in verdict.reasons)


@pytest.mark.unit
def test_solo_below_preferred_rr_needs_higher_quality() -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
        AdvisoryVote,
    )
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )

    pack = tuple(
        StrategyEvaluation(
            strategy_id=sid,
            name=sid,
            symbol="XAUUSD",
            direction="BUY" if sid == "smc_scalping" else "NONE",
            passed=sid == "smc_scalping",
            quality=83 if sid == "smc_scalping" else 20,
            confidence=82 if sid == "smc_scalping" else 20,
            explanation="x",
            reject_reason=None if sid == "smc_scalping" else "fail",
            filters={},
            score_components={},
        )
        for sid in (
            "smc_scalping",
            "trend_continuation",
            "breakout_scalping",
            "range_mean_reversion",
            "momentum_scalping",
        )
    )
    # HOLD-only advisory skips score-factor collection (isolates RR gate).
    hold_only = (
        AdvisoryVote(
            "neutral", "Neutral", "HOLD", 40, "isolated", "score_factor_advisory"
        ),
    )
    # Single passer (raw_confluence=1) + RR below preferred → raised quality bar.
    verdict = orchestrate_strategies(
        pack,
        score=_base_score(net_reward_risk=1.6, mtf_alignment=75),
        advisory_votes=hold_only,
    )
    assert verdict.prefer_no_trade is True
    assert any("preferred" in r.lower() for r in verdict.reasons)
