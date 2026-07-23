"""EQS platform orchestrator — execution intelligence, advisory only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.execution_quality_suite.analytics import (
    build_alerts,
    build_broker_health,
    build_consistency,
    build_evidence_links,
    build_execution_score,
    build_execution_timelines,
    build_fill_quality,
    build_latency_analytics,
    build_reports,
    build_slippage_analytics,
)
from app.domain.execution_quality_suite.gather import gather_execution_sources
from app.domain.execution_quality_suite.models import ISOLATION_FLAGS
from app.domain.execution_quality_suite.store import EqsStore


class ExecutionQualitySuite:
    def __init__(self, store: EqsStore | None = None) -> None:
        self.store = store or EqsStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_execution_sources()
        timelines = build_execution_timelines(ctx)
        latency = build_latency_analytics(ctx)
        slippage = build_slippage_analytics(ctx)
        fills = build_fill_quality(ctx)
        consistency = build_consistency(ctx, latency)
        broker = build_broker_health(ctx)
        score = build_execution_score(
            latency=latency,
            slippage=slippage,
            fills=fills,
            consistency=consistency,
            broker=broker,
        )
        evidence = build_evidence_links(ctx)
        alerts = build_alerts(
            latency=latency,
            slippage=slippage,
            fills=fills,
            broker=broker,
            consistency=consistency,
        )
        reports = build_reports(
            latency=latency,
            slippage=slippage,
            fills=fills,
            broker=broker,
            score=score,
            alerts=alerts,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "execution_quality_suite",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "timelines": timelines,
            "latency": latency,
            "slippage": slippage,
            "fill_quality": fills,
            "consistency": consistency,
            "broker_health": broker,
            "execution_score": score,
            "evidence": evidence,
            "alerts": alerts,
            "reports": reports,
            "stats": {
                "timeline_count": len(timelines),
                "alert_count": len(alerts),
                "overall_score": score.get("overall_execution_score"),
            },
            "read_only": True,
            "never_modifies_production": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in ("daily", "weekly", "monthly"):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"eqs-{key}-{datetime.now(UTC).date()}",
                            "kind": "execution_quality",
                            **body,
                        }
                    )
            for key in ("latency_report", "slippage_report", "broker_report"):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"eqs-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "execution_dashboard": {
                "score": pack["execution_score"],
                "alerts": pack["alerts"],
                "stats": pack["stats"],
            },
            "latency_explorer": pack["latency"],
            "slippage_explorer": pack["slippage"],
            "execution_timeline": pack["timelines"][:25],
            "broker_health": pack["broker_health"],
            "execution_reports": self.store.list_reports(limit=20),
            "execution_score": pack["execution_score"],
            "evidence": pack["evidence"],
        }
        return pack
