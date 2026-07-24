"""Unit tests — Live Performance Lab v8."""

from __future__ import annotations

from types import SimpleNamespace
from decimal import Decimal

import pytest

from app.domain.institutional_trading.performance_lab.calibration import (
    CalibrationStore,
)
from app.domain.institutional_trading.performance_lab.champion_challenger import (
    DuelStore,
    champion_from_decision,
    evaluate_challenger,
    run_champion_challenger,
)
from app.domain.institutional_trading.performance_lab.config import (
    DEFAULT_LAB_CONFIG,
)
from app.domain.institutional_trading.performance_lab.opportunity_db import (
    OpportunityOutcomeStore,
)
from app.domain.institutional_trading.performance_lab.recommendations import (
    RecommendationEngine,
)
from app.domain.institutional_trading.performance_lab.trade_replay import (
    build_replay_from_decision,
)


def _decision(**kwargs):
    defaults = dict(
        direction=SimpleNamespace(value="BUY"),
        action=SimpleNamespace(value="BUY"),
        confidence=80,
        risk_score=25,
        estimated_rr=Decimal("2.0"),
        symbol="XAUUSD",
        quality=75,
        reasons=("BOS bullish", "FVG fill", "liquidity sweep"),
        entry_zone=SimpleNamespace(mid=2300, low=2299, high=2301),
        stop_zone=SimpleNamespace(mid=2290, low=2289, high=2291),
        target_zone=SimpleNamespace(mid=2320, low=2318, high=2322),
        approved_lots=Decimal("0.1"),
        confluence=SimpleNamespace(
            factors={
                "trend": 80,
                "momentum": 70,
                "liquidity": 75,
                "volatility": 50,
                "session": 85,
            }
        ),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.unit
def test_challenger_never_may_execute() -> None:
    assert DEFAULT_LAB_CONFIG.challenger_may_execute is False
    d = _decision()
    chall = evaluate_challenger(decision=d)
    assert chall.may_execute is False
    assert chall.profile == "challenger"
    champ = champion_from_decision(d)
    assert champ.may_execute is True
    assert champ.profile == "champion"


@pytest.mark.unit
def test_champion_challenger_consistency_and_store(tmp_path) -> None:
    d = _decision()
    duel = run_champion_challenger(decision=d, trace_id="t1")
    assert duel is not None
    assert duel.challenger_executed is False
    assert duel.champion["direction"] in {"BUY", "SELL", "NONE"}
    assert duel.challenger["may_execute"] is False
    store = DuelStore()
    store._path = tmp_path / "duels.jsonl"
    store.record(duel)
    assert store.summary()["challenger_executions"] == 0


@pytest.mark.unit
def test_duel_store_rejects_challenger_execution(tmp_path) -> None:
    from app.domain.institutional_trading.performance_lab.champion_challenger import (
        ChampionChallengerDuel,
    )

    store = DuelStore()
    store._path = tmp_path / "duels2.jsonl"
    bad = ChampionChallengerDuel(
        id="x",
        at="t",
        symbol="XAUUSD",
        session="london",
        regime="trend",
        trace_id=None,
        champion={},
        challenger={},
        agree_direction=True,
        confidence_delta=0,
        score_delta=0,
        challenger_executed=True,
    )
    with pytest.raises(RuntimeError):
        store.record(bad)


@pytest.mark.unit
def test_replay_generation_has_frames() -> None:
    d = _decision()
    replay = build_replay_from_decision(
        decision=d, ticket="123", entry=2300.0, trail_events=[{"label": "BE", "detail": "moved BE"}]
    )
    assert replay.symbol == "XAUUSD"
    assert replay.bos is not None or "BOS" in replay.ai_reasoning.upper()
    assert len(replay.frames) >= 3
    labels = [f.label for f in replay.frames]
    assert "ENTRY" in labels
    assert "BE" in labels or "TRAIL" in labels or any("BE" in x for x in labels)


@pytest.mark.unit
def test_confidence_calibration_flags() -> None:
    store = CalibrationStore()
    # Overconfident at 90: predicted 90, actual ~50
    for _ in range(10):
        store.record(confidence=90, win=False)
    for _ in range(10):
        store.record(confidence=90, win=True)
    chart = store.chart()
    point = next(p for p in chart["points"] if p["predicted_confidence"] == 90)
    assert point["samples"] == 20
    assert point["actual_win_rate"] == 50.0
    assert point["status"] == "overconfident"


@pytest.mark.unit
def test_opportunity_storage_includes_skips(tmp_path) -> None:
    store = OpportunityOutcomeStore()
    store._path = tmp_path / "opp.jsonl"
    store.record_evaluation(
        symbol="EURUSD",
        ai_confidence=70,
        opportunity_score=65,
        traded=False,
        skip_reason="below_threshold",
        hypothetical_outcome="win",
    )
    store.record_evaluation(
        symbol="XAUUSD",
        ai_confidence=85,
        opportunity_score=88,
        traded=True,
        outcome="win",
        pnl=12.5,
        strategy="scalping",
    )
    snap = store.summary()
    assert snap["total"] == 2
    assert snap["skipped"] == 1
    assert snap["traded"] == 1


@pytest.mark.unit
def test_recommendation_engine_never_auto_applies() -> None:
    eng = RecommendationEngine()
    recs = eng.generate_from_rankings(
        {
            "best_symbols": [{"symbol": "XAUUSD", "profit_factor": 2.1}],
            "worst_symbols": [{"symbol": "GBPUSD", "profit_factor": 0.4}],
            "most_profitable_session": {"session": "asian", "total_pnl": -5},
            "highest_slippage": [{"symbol": "NAS100", "avg_slippage": 1.2}],
        }
    )
    assert recs
    assert all(r.auto_applied is False for r in recs)
    assert any("GBPUSD" in r.message for r in recs)


@pytest.mark.unit
def test_performance_lab_dashboard_shape() -> None:
    from app.application.services.performance_lab import build_performance_lab_dashboard

    dash = build_performance_lab_dashboard()
    assert dash["version"].startswith("performance-lab-v8")
    assert dash["safeguards"]["challenger_may_execute"] is False
    assert dash["safeguards"]["recommendations_auto_applied"] is False
    for key in (
        "champion_vs_challenger",
        "confidence_calibration",
        "opportunity_replay",
        "strategy_comparison",
        "portfolio_heatmap",
        "symbol_rankings",
        "adaptive_recommendations",
    ):
        assert key in dash
