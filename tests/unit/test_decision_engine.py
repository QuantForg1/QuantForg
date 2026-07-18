"""Unit tests for Decision Engine — wait bias, no fabricated quotes."""

from __future__ import annotations

from uuid import uuid4

from app.domain.decision_engine.explanation import build_explanation
from app.domain.decision_engine.mtf import summarize_mtf
from app.domain.decision_engine.paper_tracker import DecisionPaperTracker
from app.domain.decision_engine.risk_limits import assess_decision_risk
from app.domain.decision_engine.scoring import (
    MIN_SCORE_FOR_IDEA,
    compute_trade_score,
)


def test_mtf_insufficient() -> None:
    result = summarize_mtf({"M5": {"status": "unavailable"}})
    assert result["aligned"] is False
    assert result["status"] == "insufficient"


def test_mtf_aligned_bullish() -> None:
    frames = {
        tf: {
            "status": "available",
            "trend": "Bullish",
            "momentum": "Strong up",
            "confidence_pct": 80,
        }
        for tf in ("M5", "M15", "H1", "H4", "D1")
    }
    result = summarize_mtf(frames)
    assert result["aligned"] is True
    assert result["bias"] == "Bullish"


def test_score_defaults_to_wait() -> None:
    result = compute_trade_score(
        mtf={"aligned": False, "why": "not aligned"},
        structure={"confidence_pct": 40, "trend": "Neutral"},
        spread_ok=None,
        volatility="High",
        session_ok=False,
        news_risk="high",
        correlation_risk="high",
        portfolio_heat="hot",
        execution_quality="weak",
    )
    assert result["decision"] == "WAIT"
    assert result["bias_to_wait"] is True
    assert result["trade_score"] < MIN_SCORE_FOR_IDEA


def test_score_trade_idea_when_strong() -> None:
    result = compute_trade_score(
        mtf={"aligned": True, "bias": "Bullish", "confirmations": 5, "why": "aligned"},
        structure={"confidence_pct": 85, "trend": "Bullish"},
        spread_ok=True,
        volatility="Low",
        session_ok=True,
        news_risk="low",
        correlation_risk="low",
        portfolio_heat="cool",
        execution_quality="strong",
    )
    assert result["decision"] == "TRADE_IDEA"
    assert result["trade_score"] >= MIN_SCORE_FOR_IDEA


def test_risk_rejects_hot_portfolio() -> None:
    result = assess_decision_risk(
        account={
            "equity": 10000,
            "balance": 10000,
            "margin": 100,
            "free_margin": 9000,
            "leverage": 100,
        },
        positions=[{"symbol": "EURUSD", "volume": 1, "profit": -400}] * 5,
        atr=0.001,
        price=1.1,
        side="Bullish",
    )
    assert result["accepted"] is False
    assert result["rejects"]


def test_risk_sizes_when_healthy() -> None:
    result = assess_decision_risk(
        account={
            "equity": 10000,
            "balance": 10000,
            "margin": 50,
            "free_margin": 9000,
            "leverage": 100,
        },
        positions=[],
        atr=0.0012,
        price=1.085,
        side="Bullish",
    )
    assert result["accepted"] is True
    assert result["lot_size"] is not None
    assert result["suggested_stop"] is not None
    assert result["expected_rr"] == 2.0


def test_explanation_wait() -> None:
    exp = build_explanation(
        decision="WAIT",
        score={"supporting_factors": [], "penalties": ["weak"]},
        mtf={"aligned": False},
        structure={},
        risk={"warnings": []},
        news_risk="low",
    )
    assert "WAIT" in exp["summary"]
    assert exp["what_would_improve_it"]


def test_paper_tracker_performance() -> None:
    t = DecisionPaperTracker()
    uid = uuid4()
    for pnl in (10, -5, 8, -3, 12):
        row = t.record(
            user_id=uid,
            symbol="EURUSD",
            decision="TRADE_IDEA",
            side="Bullish",
            score=80,
            confidence=75,
            expected_rr=2,
            simulated_pnl=pnl,
        )
        assert row["mode"] == "paper"
    # waits should not affect win rate sample
    t.record(
        user_id=uid,
        symbol="EURUSD",
        decision="WAIT",
        side=None,
        score=40,
        confidence=40,
    )
    perf = t.performance(uid)
    assert perf["status"] == "available"
    assert perf["sample_size"] == 5
    assert perf["win_rate"] == 0.6
    reports = t.reports(uid)
    assert reports["daily"]["waits"] >= 1
