"""Unit tests — Quant Knowledge Graph (read-only)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quant_knowledge_graph.builder import build_graph
from app.domain.quant_knowledge_graph.models import ISOLATION_FLAGS, NodeType, RelationType
from app.domain.quant_knowledge_graph.platform import QuantKnowledgeGraph
from app.domain.quant_knowledge_graph.query import (
    ai_query,
    evidence_chain,
    impact_analysis,
    recommendation_trace,
    root_cause_graph,
    search_knowledge,
)
from app.domain.quant_knowledge_graph.store import QkgStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "idw": {
                "signals": [
                    {"id": "s1", "symbol": "XAUUSD", "session": "london"},
                ],
                "trades": [
                    {"id": "t1", "symbol": "XAUUSD", "ticket": 101},
                ],
                "regimes": [{"regime": "TRENDING"}],
            },
            "irl": {
                "experiments": [
                    {
                        "uuid": "e1",
                        "name": "Exp A",
                        "verdict": "Research Passed",
                    }
                ],
                "jobs": [{"id": "j1", "experiment_id": "e1", "name": "replay-1"}],
            },
            "aqs": {
                "recommendations": [
                    {
                        "id": "r1",
                        "title": "Improve confluence band",
                        "status": "Open",
                    }
                ],
                "reports": [{"report_id": "rep1", "title": "Weekly"}],
            },
            "portfolio": {
                "sections": {
                    "performance": {"profit_factor": 1.5, "trade_count": 10},
                    "risk": {"max_drawdown_pct": 7.0},
                }
            },
            "regime": {"current": {"current_regime": "TRENDING"}},
            "diagnostics": {
                "cycles": [
                    {
                        "cycle_id": "c1",
                        "outcome": "risk rejected",
                        "block_reason": "risk",
                    }
                ]
            },
            "icc": {"alerts": [{"id": "a1", "message": "latency spike"}]},
            "sic": {"strategies": [{"id": "cand1", "name": "Candidate"}]},
            "audit": [{"id": "au1", "event_type": "governance_check"}],
        },
        "availability": {"idw": True, "irl": True, "aqs": True},
    }


class TestQkgBuilderQuery:
    def test_build_nodes_and_relations(self) -> None:
        g = build_graph(_ctx())
        assert g["stats"]["node_count"] >= 10
        assert g["stats"]["edge_count"] >= 5
        types = {n["type"] for n in g["nodes"]}
        assert NodeType.TRADE.value in types
        assert NodeType.SIGNAL.value in types
        assert NodeType.RECOMMENDATION.value in types
        rels = {e["relation"] for e in g["edges"]}
        assert RelationType.GENERATED_BY.value in rels
        assert g["never_modifies_production"] is True

    def test_search_evidence_root_cause_impact(self) -> None:
        g = build_graph(_ctx())
        hits = search_knowledge(g, q="XAUUSD", limit=10)
        assert hits
        chain = evidence_chain(g, "recommendation:r1")
        assert chain["start"] is not None
        rc = root_cause_graph(g, "strategy:production")
        assert rc["subject"] is not None
        impact = impact_analysis(g, "strategy:production")
        assert "impacted" in impact
        trace = recommendation_trace(g, "r1")
        assert trace["recommendation"] is not None
        assert trace["never_applies_production"] is True

    def test_ai_query(self) -> None:
        g = build_graph(_ctx())
        ans = ai_query(g, "find Recommendations")
        assert ans["capability"] == "knowledge_search"
        assert ans["never_modifies_production"] is True
        ans2 = ai_query(g, "root cause", node_id="strategy:production")
        assert ans2["capability"] == "root_cause_graph"


class TestQkgPlatform:
    def test_isolation_and_perf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ISOLATION_FLAGS["mutates_production"] is False
        assert ISOLATION_FLAGS["modifies_thresholds"] is False
        qkg = QuantKnowledgeGraph(store=QkgStore(path=tmp_path / "qkg.json"))
        monkeypatch.setattr(
            "app.domain.quant_knowledge_graph.platform.gather_knowledge_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = qkg.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["stats"]["node_count"] > 0
        assert elapsed < 45
        ai = qkg.query_for_ai("search Alerts")
        assert ai["result"]["count"] >= 0
