"""Unit tests — QuantForg Decision Intelligence Engine."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_decision_intelligence.analytics import (
    build_evidence_graph,
    build_recommendations,
    build_scores,
    decision_consistency_check,
    evidence_consistency_check,
    explainability_validation,
)
from app.domain.quantforg_decision_intelligence.models import (
    DATA_SOURCES,
    DECISION_CATEGORIES,
    ISOLATION_FLAGS,
    SCORE_KEYS,
)
from app.domain.quantforg_decision_intelligence.platform import (
    QuantForgDecisionIntelligenceEngine,
)
from app.domain.quantforg_decision_intelligence.store import QdieStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "irl": {"experiments": [{"experiment_id": "e0"}], "jobs": []},
            "replay": {"simulations": []},
            "ise": {"simulations": [{"simulation_id": "s1", "mode": "Monte Carlo"}]},
            "iep": {"registry": [{"experiment_id": "e1"}], "snapshot": {}},
            "cvf": {"confidence": {"confidence": 42}},
            "irap": {
                "metrics": {"maximum_drawdown": 28},
                "alerts": [{"kind": "drawdown", "severity": "warning"}],
            },
            "eqs": {"execution_score": {"overall_execution_score": 68}},
            "res": {"reliability_score": {"overall_reliability_score": 70}},
            "qcs": {
                "level": {"level": "Not Ready"},
                "scores": {"overall_institutional_readiness_score": 48},
            },
            "qpm": {
                "metrics": {"portfolio_confidence_score": 52},
                "health": {"overall_portfolio_health": 50},
            },
            "islm": {
                "registry": [{"strategy_id": "st1", "lifecycle_state": "Research"}],
                "approvals": [],
            },
            "irdp": {"releases": [{"release_id": "r1", "status": "draft"}], "approvals": []},
            "icp": {"health": {"overall_platform_health": 58}, "alerts": []},
            "aoc": {
                "executive_scores": {"operational_readiness": 55},
                "recommendations": [{"recommendation_id": "a1"}],
            },
            "qkg": {"nodes": []},
            "qem": {"stats": {"event_count": 3}},
            "qcdm": {"schema_version": "1.0.0"},
        },
        "availability": {s: True for s in DATA_SOURCES},
        "source_count": len(DATA_SOURCES),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["modifies_risk"] is False
        assert ISOLATION_FLAGS["approves_releases"] is False
        assert ISOLATION_FLAGS["allocates_capital"] is False
        assert ISOLATION_FLAGS["performs_automatic_actions"] is False
        assert ISOLATION_FLAGS["human_approval_required"] is True
        assert ISOLATION_FLAGS["advisory_only"] is True


class TestDecisionConsistency:
    def test_recs_scores_explainability(self) -> None:
        ctx = _ctx()
        scores = build_scores(ctx)
        for key in SCORE_KEYS:
            assert key in scores
            assert 0.0 <= scores[key] <= 100.0
        recs = build_recommendations(ctx, scores)
        assert recs
        assert all(r["decision_category"] in DECISION_CATEGORIES for r in recs)
        assert all(r.get("requires_human_approval") for r in recs)
        assert all(r.get("auto_applied") is False for r in recs)
        assert decision_consistency_check(recs)["ok"] is True
        graph = build_evidence_graph(ctx, recs)
        assert evidence_consistency_check(recs, graph)["ok"] is True
        assert explainability_validation(recs)["ok"] is True


class TestPlatform:
    def test_dashboard(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        qdie = QuantForgDecisionIntelligenceEngine(
            store=QdieStore(path=tmp_path / "qdie.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_decision_intelligence.platform.gather_decision_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = qdie.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_modifies_strategies"] is True
        assert pack["never_approves_releases"] is True
        assert pack["never_allocates_capital"] is True
        assert pack["never_modifies_risk"] is True
        assert pack["never_performs_automatic_actions"] is True
        assert pack["human_approval_required"] is True
        assert pack["decision_consistency"]["ok"] is True
        assert pack["evidence_consistency"]["ok"] is True
        assert pack["explainability_validation"]["ok"] is True
        assert pack["sections"]["decision_center"]
        assert pack["sections"]["recommendation_explorer"]
        assert pack["sections"]["evidence_graph"]
        assert pack["sections"]["tradeoff_viewer"]
        assert pack["sections"]["executive_decision_dashboard"]
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
