"""QDIE platform — advisory decision intelligence, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_decision_intelligence.analytics import (
    build_evidence_graph,
    build_recommendations,
    build_reports,
    build_scores,
    build_tradeoff_viewer,
    decision_consistency_check,
    evidence_consistency_check,
    explainability_validation,
)
from app.domain.quantforg_decision_intelligence.gather import gather_decision_sources
from app.domain.quantforg_decision_intelligence.models import ISOLATION_FLAGS
from app.domain.quantforg_decision_intelligence.store import QdieStore


class QuantForgDecisionIntelligenceEngine:
    def __init__(self, store: QdieStore | None = None) -> None:
        self.store = store or QdieStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_decision_sources()
        scores = build_scores(ctx)
        recommendations = build_recommendations(ctx, scores)
        evidence_graph = build_evidence_graph(ctx, recommendations)
        tradeoffs = build_tradeoff_viewer(recommendations)
        reports = build_reports(
            scores=scores,
            recommendations=recommendations,
            evidence_graph=evidence_graph,
        )
        decision_consistency = decision_consistency_check(recommendations)
        evidence_consistency = evidence_consistency_check(
            recommendations, evidence_graph
        )
        explainability = explainability_validation(recommendations)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_decision_intelligence",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "scores": scores,
            "recommendations": recommendations,
            "evidence_graph": evidence_graph,
            "tradeoffs": tradeoffs,
            "reports": reports,
            "decision_consistency": decision_consistency,
            "evidence_consistency": evidence_consistency,
            "explainability_validation": explainability,
            "read_only": True,
            "advisory_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "never_approves_releases": True,
            "never_allocates_capital": True,
            "never_modifies_risk": True,
            "never_performs_automatic_actions": True,
            "human_approval_required": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "decision_report",
                "executive_decision_brief",
                "recommendation_summary",
                "decision_history",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qdie-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "decision_center": {
                "scores": pack["scores"],
                "recommendations_preview": pack["recommendations"][:8],
            },
            "recommendation_explorer": pack["recommendations"],
            "evidence_graph": pack["evidence_graph"],
            "tradeoff_viewer": pack["tradeoffs"],
            "executive_decision_dashboard": pack["reports"].get(
                "executive_decision_brief"
            ),
            "reports": self.store.list_reports(limit=20),
            "history": self.store.list_history(limit=50),
        }
        return pack
