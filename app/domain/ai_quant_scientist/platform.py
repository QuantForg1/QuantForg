"""AQS platform orchestrator."""

from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime
from typing import Any

from app.domain.ai_quant_scientist.analysis import (
    build_executive_report,
    build_recommendations,
    compare_strategies,
    detect_weaknesses,
    discover_patterns,
    parameter_sensitivity,
    regime_research,
)
from app.domain.ai_quant_scientist.gather import gather_research_context
from app.domain.ai_quant_scientist.models import ISOLATION_FLAGS, RecommendationStatus
from app.domain.ai_quant_scientist.nli import answer_question
from app.domain.ai_quant_scientist.store import AqsStore


class AiQuantScientist:
    def __init__(self, store: AqsStore | None = None) -> None:
        self.store = store or AqsStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run_research(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_research_context()
        patterns = discover_patterns(ctx)
        weaknesses = detect_weaknesses(ctx)
        comparison = compare_strategies(ctx)
        regimes = regime_research(ctx)
        sensitivity = parameter_sensitivity(ctx)
        recommendations = build_recommendations(
            patterns=patterns,
            weaknesses=weaknesses,
            comparison=comparison,
            regimes=regimes,
            sensitivity=sensitivity,
        )

        if persist:
            for rec in recommendations:
                self.store.upsert_recommendation(rec)

        stored = self.store.list_recommendations(limit=100)
        # Prefer stored (may have Accepted/Rejected) merged by id
        by_id = {r["id"]: r for r in recommendations}
        for s in stored:
            if s["id"] in by_id:
                by_id[s["id"]] = {**by_id[s["id"]], **s}
            else:
                by_id[s["id"]] = s
        merged = list(by_id.values())
        merged.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)

        score_vals = [
            (r.get("scores") or {}).get("research_confidence_score")
            for r in merged
            if (r.get("scores") or {}).get("research_confidence_score") is not None
        ]
        scores_avg = {
            "research_confidence_score": round(statistics.mean(score_vals), 1)
            if score_vals
            else 50.0,
            "evidence_strength": round(
                statistics.mean(
                    [
                        (r.get("scores") or {}).get("evidence_strength") or 50
                        for r in merged
                    ]
                ),
                1,
            )
            if merged
            else 50.0,
            "statistical_reliability": round(
                statistics.mean(
                    [
                        (r.get("scores") or {}).get("statistical_reliability") or 50
                        for r in merged
                    ]
                ),
                1,
            )
            if merged
            else 50.0,
            "recommendation_strength": round(
                statistics.mean(
                    [
                        (r.get("scores") or {}).get("recommendation_strength") or 50
                        for r in merged
                    ]
                ),
                1,
            )
            if merged
            else 50.0,
        }

        report = build_executive_report(
            patterns=patterns,
            weaknesses=weaknesses,
            comparison=comparison,
            recommendations=merged,
            scores_avg=scores_avg,
        )
        report["charts"]["sensitivity_stable"] = sensitivity.get("most_stable")
        if persist:
            self.store.save_report(report)

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "schema_version": "1.0.0",
            "mode": "ai_quant_scientist",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "patterns": patterns,
            "weaknesses": weaknesses,
            "comparison": comparison,
            "regimes": regimes,
            "sensitivity": sensitivity,
            "recommendations": merged,
            "institutional_scores": scores_avg,
            "latest_report": report,
            "feed": merged[:15],
        }

    def dashboard(self) -> dict[str, Any]:
        pack = self.run_research(persist=True)
        pack["sections"] = {
            "research_feed": pack["feed"],
            "recommendation_center": {
                "open": [r for r in pack["recommendations"] if r.get("status") == "Open"],
                "accepted": [
                    r for r in pack["recommendations"] if r.get("status") == "Accepted"
                ],
                "rejected": [
                    r for r in pack["recommendations"] if r.get("status") == "Rejected"
                ],
                "archived": [
                    r for r in pack["recommendations"] if r.get("status") == "Archived"
                ],
            },
            "pattern_explorer": pack["patterns"],
            "strategy_comparator": pack["comparison"],
            "explainability": [
                {"id": r["id"], "title": r["title"], "explainability": r.get("explainability")}
                for r in pack["recommendations"][:20]
            ],
            "executive_reports": self.store.list_reports(limit=10),
            "institutional_scores": pack["institutional_scores"],
        }
        return pack

    def ask(self, question: str) -> dict[str, Any]:
        pack = self.run_research(persist=False)
        return answer_question(question, pack=pack)

    def set_recommendation_status(self, rid: str, status: str) -> dict[str, Any] | None:
        """Human governance only — never applies to production engines."""
        if status not in {s.value for s in RecommendationStatus}:
            raise ValueError("invalid_status")
        return self.store.set_status(rid, status)
