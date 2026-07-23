"""QKG platform orchestrator."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quant_knowledge_graph.builder import build_graph
from app.domain.quant_knowledge_graph.gather import gather_knowledge_sources
from app.domain.quant_knowledge_graph.models import ISOLATION_FLAGS
from app.domain.quant_knowledge_graph.query import (
    ai_query,
    dependency_viewer,
    evidence_chain,
    historical_lineage,
    impact_analysis,
    recommendation_trace,
    relationships_for,
    root_cause_graph,
    search_knowledge,
)
from app.domain.quant_knowledge_graph.store import QkgStore


class QuantKnowledgeGraph:
    def __init__(self, store: QkgStore | None = None) -> None:
        self.store = store or QkgStore()
        self.isolation = dict(ISOLATION_FLAGS)
        self._graph: dict[str, Any] | None = None

    def rebuild(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_knowledge_sources()
        graph = build_graph(ctx)
        graph["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        graph["isolation"] = self.isolation
        self._graph = graph
        if persist:
            self.store.save_snapshot(graph)
        return graph

    def graph(self, *, refresh: bool = False) -> dict[str, Any]:
        if refresh or self._graph is None:
            cached = self.store.get_snapshot()
            if cached.get("nodes") and not refresh:
                self._graph = {
                    **cached,
                    "isolation": self.isolation,
                    "read_only": True,
                    "never_modifies_production": True,
                }
            else:
                return self.rebuild(persist=True)
        return self._graph or self.rebuild(persist=True)

    def dashboard(self) -> dict[str, Any]:
        g = self.graph(refresh=True)
        return {
            "schema_version": "1.0.0",
            "mode": "quant_knowledge_graph",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "stats": g.get("stats"),
            "availability": g.get("availability"),
            "elapsed_ms": g.get("elapsed_ms"),
            "sample_nodes": (g.get("nodes") or [])[:20],
            "sample_edges": (g.get("edges") or [])[:30],
            "sections": {
                "knowledge_search": {"hint": "GET /qkg/search?q="},
                "relationship_viewer": {"hint": "GET /qkg/relationships/{id}"},
                "evidence_chains": {"hint": "GET /qkg/evidence/{id}"},
                "root_cause": {"hint": "GET /qkg/root-cause/{id}"},
                "ai_query": {"hint": "GET /qkg/ai?q="},
            },
            "read_only": True,
            "never_modifies_production": True,
            "nodes": g.get("nodes"),
            "edges": g.get("edges"),
        }

    def search(self, *, q: str | None = None, node_type: str | None = None, limit: int = 50) -> dict[str, Any]:
        g = self.graph()
        hits = search_knowledge(g, q=q, node_type=node_type, limit=limit)
        return {"matches": hits, "count": len(hits), "isolation": self.isolation}

    def relationships(self, node_id: str) -> dict[str, Any]:
        return {**relationships_for(self.graph(), node_id), "isolation": self.isolation}

    def dependencies(self, node_id: str, *, depth: int = 3) -> dict[str, Any]:
        return {**dependency_viewer(self.graph(), node_id, depth=depth), "isolation": self.isolation}

    def evidence(self, node_id: str) -> dict[str, Any]:
        return {**evidence_chain(self.graph(), node_id), "isolation": self.isolation}

    def recommendation_trace(self, recommendation_id: str) -> dict[str, Any]:
        return {
            **recommendation_trace(self.graph(), recommendation_id),
            "isolation": self.isolation,
        }

    def lineage(self, node_id: str) -> dict[str, Any]:
        return {**historical_lineage(self.graph(), node_id), "isolation": self.isolation}

    def impact(self, node_id: str) -> dict[str, Any]:
        return {**impact_analysis(self.graph(), node_id), "isolation": self.isolation}

    def root_cause(self, node_id: str) -> dict[str, Any]:
        return {**root_cause_graph(self.graph(), node_id), "isolation": self.isolation}

    def query_for_ai(self, question: str, *, node_id: str | None = None) -> dict[str, Any]:
        """Public entry for AQS / AQC — read-only graph answers."""
        return {
            **ai_query(self.graph(), question, node_id=node_id),
            "isolation": self.isolation,
        }
