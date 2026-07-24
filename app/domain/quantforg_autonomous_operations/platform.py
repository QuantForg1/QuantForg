"""AOC platform — operational orchestration, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_autonomous_operations.analytics import (
    build_evidence_explorer,
    build_executive_scores,
    build_operational_health,
    build_recommendations,
    build_reports,
    build_watch_modules,
    build_work_queue,
    evidence_integrity_check,
    recommendation_consistency_check,
)
from app.domain.quantforg_autonomous_operations.gather import gather_operations_sources
from app.domain.quantforg_autonomous_operations.models import ISOLATION_FLAGS
from app.domain.quantforg_autonomous_operations.store import AocStore


class QuantForgAutonomousOperationsCenter:
    def __init__(self, store: AocStore | None = None) -> None:
        self.store = store or AocStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_operations_sources()
        health = build_operational_health(ctx)
        watches = build_watch_modules(ctx)
        recommendations = build_recommendations(ctx, watches)
        work_queue = build_work_queue(recommendations)
        executive_scores = build_executive_scores(ctx, health, watches)
        evidence = build_evidence_explorer(ctx)
        reports = build_reports(
            scores=executive_scores,
            recommendations=recommendations,
            queue=work_queue,
            health=health,
            watches=watches,
            evidence=evidence,
        )
        rec_consistency = recommendation_consistency_check(recommendations)
        evidence_integrity = evidence_integrity_check(
            evidence=evidence, scores=executive_scores, queue=work_queue
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_autonomous_operations",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "operational_health": health,
            "watches": watches,
            "recommendations": recommendations,
            "work_queue": work_queue,
            "executive_scores": executive_scores,
            "evidence": evidence,
            "reports": reports,
            "recommendation_consistency": rec_consistency,
            "evidence_integrity": evidence_integrity,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "never_modifies_risk": True,
            "never_modifies_safety": True,
            "never_approves_releases": True,
            "never_allocates_capital": True,
            "never_deploys_strategies": True,
            "never_performs_automatic_remediation": True,
            "human_approval_required_for_recommendations": True,
            "preserves_existing_safety_guarantees": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "daily_operations_brief",
                "weekly_executive_brief",
                "platform_readiness_report",
                "recommendation_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"aoc-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "operations_dashboard": {
                "operational_health": pack["operational_health"],
                "executive_scores": pack["executive_scores"],
                "queue_preview": pack["work_queue"][:8],
            },
            "recommendation_center": pack["recommendations"],
            "operational_queue": pack["work_queue"],
            "executive_brief": {
                "scores": pack["executive_scores"],
                "watches": {
                    "risk": pack["watches"].get("risk_watch"),
                    "validation": pack["watches"].get("validation_watch"),
                    "portfolio": pack["watches"].get("portfolio_watch"),
                    "release": pack["watches"].get("release_readiness"),
                },
            },
            "evidence_explorer": pack["evidence"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack
