"""ICP platform — executive aggregation, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_control_plane.analytics import (
    aggregation_consistency_check,
    build_dependency_map,
    build_evidence_center,
    build_executive_alerts,
    build_global_timeline,
    build_health_scores,
    build_reports,
)
from app.domain.institutional_control_plane.gather import gather_control_plane_sources
from app.domain.institutional_control_plane.models import ISOLATION_FLAGS, SUBSYSTEMS
from app.domain.institutional_control_plane.store import IcpStore


class InstitutionalControlPlane:
    def __init__(self, store: IcpStore | None = None) -> None:
        self.store = store or IcpStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_control_plane_sources()
        health = build_health_scores(ctx)
        alerts = build_executive_alerts(ctx, health)
        timeline = build_global_timeline(ctx)
        dependencies = build_dependency_map(ctx)
        evidence = build_evidence_center(ctx)
        reports = build_reports(
            health=health,
            alerts=alerts,
            timeline=timeline,
            dependencies=dependencies,
            evidence=evidence,
        )
        consistency = aggregation_consistency_check(
            health=health, alerts=alerts, evidence=evidence
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "institutional_control_plane",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
                "subsystems": list(SUBSYSTEMS),
            },
            "health": health,
            "alerts": alerts,
            "timeline": timeline,
            "dependencies": dependencies,
            "evidence": evidence,
            "reports": reports,
            "aggregation_consistency": consistency,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategy": True,
            "never_modifies_risk": True,
            "never_modifies_releases": True,
            "never_approves_experiments": True,
            "never_approves_lifecycle_transitions": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "executive_daily_brief",
                "weekly_operations_review",
                "monthly_platform_review",
                "quarterly_executive_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"icp-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "executive_dashboard": {
                "health": pack["health"],
                "alerts": pack["alerts"][:12],
            },
            "global_timeline": pack["timeline"],
            "health_center": pack["health"],
            "dependency_explorer": pack["dependencies"],
            "evidence_center": pack["evidence"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack
