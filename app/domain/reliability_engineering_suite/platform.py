"""RES platform orchestrator — reliability engineering, advisory only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.reliability_engineering_suite.analytics import (
    build_availability,
    build_evidence,
    build_failure_analysis,
    build_platform_health,
    build_recovery_analytics,
    build_reliability_score,
    build_reliability_trends,
    build_reports,
    build_service_reliability,
)
from app.domain.reliability_engineering_suite.gather import gather_reliability_sources
from app.domain.reliability_engineering_suite.models import ISOLATION_FLAGS
from app.domain.reliability_engineering_suite.store import ResStore


class ReliabilityEngineeringSuite:
    def __init__(self, store: ResStore | None = None) -> None:
        self.store = store or ResStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_reliability_sources()
        services = build_service_reliability(ctx)
        failures = build_failure_analysis(ctx)
        recovery = build_recovery_analytics(ctx)
        availability = build_availability(ctx, services)
        eqs_snap = (ctx.get("sources") or {}).get("eqs") or {}
        score = build_reliability_score(
            availability=availability,
            recovery=recovery,
            failures=failures,
            services=services,
            eqs_snapshot=eqs_snap if isinstance(eqs_snap, dict) else {},
        )
        trends = build_reliability_trends(
            ctx,
            availability=availability,
            recovery=recovery,
            failures=failures,
            services=services,
        )
        platform_health = build_platform_health(
            score=score,
            availability=availability,
            services=services,
            failures=failures,
        )
        evidence = build_evidence(ctx)
        reports = build_reports(
            platform_health=platform_health,
            services=services,
            availability=availability,
            recovery=recovery,
            failures=failures,
            score=score,
            trends=trends,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "reliability_engineering_suite",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "platform_health": platform_health,
            "services": services,
            "availability_windows": availability,
            "recovery": recovery,
            "failures": failures,
            "trends": trends,
            "reliability_score": score,
            "evidence": evidence,
            "reports": reports,
            "read_only": True,
            "never_modifies_production": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in ("daily", "weekly", "monthly", "incident_summary"):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"res-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "reliability_dashboard": pack["platform_health"],
            "health_explorer": pack["services"],
            "recovery_explorer": pack["recovery"],
            "failure_explorer": pack["failures"],
            "reliability_reports": self.store.list_reports(limit=20),
            "reliability_score": pack["reliability_score"],
            "trends": pack["trends"],
            "evidence": pack["evidence"],
        }
        return pack
