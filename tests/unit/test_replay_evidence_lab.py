"""Unit tests — Institutional Replay & Evidence Lab (advisory only)."""

from __future__ import annotations

import pytest

from app.domain.replay_evidence_lab.confidence import confidence_level, score_kpi
from app.domain.replay_evidence_lab.counterfactual import evaluate_counterfactual
from app.domain.replay_evidence_lab.evidence_store import EvidenceDatabase
from app.domain.replay_evidence_lab.gates import evaluate_evidence_gates
from app.domain.replay_evidence_lab.lab import build_replay_evidence_lab
from app.domain.replay_evidence_lab.replay import run_replay


def _bars() -> list[dict]:
    return [
        {
            "timestamp": "2026-07-20T08:00:00+00:00",
            "open": 2400.0,
            "high": 2405.0,
            "low": 2398.0,
            "close": 2402.0,
        },
        {
            "timestamp": "2026-07-20T08:05:00+00:00",
            "open": 2402.0,
            "high": 2410.0,
            "low": 2401.0,
            "close": 2408.0,
        },
        {
            "timestamp": "2026-07-20T08:10:00+00:00",
            "open": 2408.0,
            "high": 2412.0,
            "low": 2395.0,
            "close": 2396.0,
        },
    ]


def _opportunities() -> list[dict]:
    return [
        {
            "timestamp": "2026-07-20T08:00:00+00:00",
            "session": "london",
            "market_regime": "trend",
            "trend": "bullish",
            "bos": True,
            "choch": False,
            "liquidity_sweep": True,
            "order_block": True,
            "fair_value_gap": False,
            "confluence_score": 92,
            "decision": "BUY",
            "direction": "BUY",
            "entry": 2402.0,
            "exit": 2410.0,
            "rr": 2.0,
            "hold_time": 300,
        },
        {
            "timestamp": "2026-07-20T08:05:00+00:00",
            "session": "london",
            "market_regime": "high_volatility",
            "trend": "bullish",
            "bos": False,
            "choch": True,
            "liquidity_sweep": False,
            "order_block": False,
            "fair_value_gap": True,
            "confluence_score": 78,
            "decision": "NO_TRADE",
            "no_trade_reason": "spread too wide",
            "direction": "BUY",
            "entry": 2408.0,
            "stop_loss": 2400.0,
            "take_profit": 2420.0,
            "bars_after": [
                {"high": 2415.0, "low": 2405.0},
                {"high": 2418.0, "low": 2399.0},
            ],
        },
    ]


@pytest.mark.unit
class TestReplayEvidenceLab:
    def test_replay_records_fields(self) -> None:
        result = run_replay(bars=_bars(), opportunities=_opportunities())
        assert result["status"] == "available"
        assert result["bars_loaded"] == 3
        assert result["opportunities_recorded"] == 2
        opp = result["opportunities"][0]
        assert opp["bos"] is True
        assert opp["session"] == "london"
        assert opp["confluence_score"] == 92.0
        assert opp["decision"] == "BUY"

    def test_counterfactual_sl_first_research_only(self) -> None:
        cf = evaluate_counterfactual(
            direction="BUY",
            entry=2408.0,
            stop_loss=2400.0,
            take_profit=2420.0,
            bars_after=[
                {"high": 2415.0, "low": 2405.0},
                {"high": 2418.0, "low": 2399.0},
            ],
        )
        assert cf["research_only"] is True
        assert cf["feeds_production_kpis"] is False
        assert cf["result"] == "sl_first"

    def test_counterfactual_never_invents_bars(self) -> None:
        cf = evaluate_counterfactual(
            direction="BUY",
            entry=2400.0,
            stop_loss=2390.0,
            take_profit=2410.0,
            bars_after=None,
        )
        assert cf["status"] == "unavailable"
        assert cf["result"] is None

    def test_lanes_never_mix(self) -> None:
        db = EvidenceDatabase()
        db.add("live", {"id": "L1"})
        db.add("demo", {"id": "D1"})
        db.add("replay", {"id": "R1"})
        db.add("research", {"id": "X1"})
        assert len(db.list("live")) == 1
        assert db.list("live")[0]["id"] == "L1"
        assert all(r["evidence_lane"] == "demo" for r in db.list("demo"))
        counts = db.counts()
        assert counts == {"live": 1, "demo": 1, "replay": 1, "research": 1}

    def test_confidence_scoring(self) -> None:
        assert confidence_level(10) == "insufficient"
        assert confidence_level(50) == "low"
        assert confidence_level(150) == "medium"
        assert confidence_level(400) == "high"
        kpi = score_kpi(
            name="win_rate",
            value=0.68,
            sample_size=312,
            required_sample=50,
        )
        assert kpi["confidence"] == "high"
        assert kpi["sample_size"] == 312
        assert kpi["coverage"] == 1.0

    def test_evidence_gates_block_strategy_recs(self) -> None:
        gates = evaluate_evidence_gates(
            live_closed_trades=3,
            replay_opportunities=2,
            no_trade_observations=1,
        )
        assert gates["all_passed"] is False
        assert gates["may_recommend_strategy_changes"] is False
        assert gates["never_auto_modifies_strategy"] is True

    def test_gates_pass_when_thresholds_met(self) -> None:
        gates = evaluate_evidence_gates(
            live_closed_trades=50,
            replay_opportunities=500,
            no_trade_observations=100,
        )
        assert gates["all_passed"] is True
        assert gates["may_recommend_strategy_changes"] is True

    def test_full_pack_advisory_only(self) -> None:
        pack = build_replay_evidence_lab(
            bars=_bars(),
            opportunities=_opportunities(),
            live_closed_trades=[{"net_pnl": 10}],
            thresholds={
                "min_live_closed_trades": 50,
                "min_replay_opportunities": 500,
                "min_no_trade_observations": 100,
            },
        )
        assert pack["advisory_only"] is True
        assert pack["never_modifies_strategy"] is True
        assert pack["never_modifies_performance_intelligence"] is True
        assert pack["counterfactual"]["research_only"] is True
        assert pack["gates"]["may_recommend_strategy_changes"] is False
        assert "reports" in pack
        assert "open_questions" in pack["reports"]
        assert isinstance(pack["recommendations"], list)
        assert pack["evidence"]["never_mix_evidence_lanes"] is True

    def test_empty_never_fabricates(self) -> None:
        pack = build_replay_evidence_lab()
        assert pack["replay"]["opportunities_recorded"] == 0
        assert pack["confidence"]["overall_confidence"] == "insufficient"
