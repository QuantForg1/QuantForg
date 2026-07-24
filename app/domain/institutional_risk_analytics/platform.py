"""IRAP platform orchestrator — portfolio risk intelligence, advisory only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_risk_analytics.analytics import (
    build_alerts,
    build_capital_allocation,
    build_concentration,
    build_core_metrics,
    build_correlation,
    build_drawdown_analytics,
    build_exposure,
    build_reports,
    build_risk_adjusted,
    build_risk_trends,
    build_scenario_risk,
    build_stress_loss,
    build_tail_risk,
)
from app.domain.institutional_risk_analytics.gather import gather_risk_sources
from app.domain.institutional_risk_analytics.models import ISOLATION_FLAGS
from app.domain.institutional_risk_analytics.store import IrapStore


class InstitutionalRiskAnalytics:
    def __init__(self, store: IrapStore | None = None) -> None:
        self.store = store or IrapStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_risk_sources()
        metrics = build_core_metrics(ctx)
        exposure = build_exposure(ctx)
        drawdown = build_drawdown_analytics(ctx)
        concentration = build_concentration(ctx, exposure)
        capital = build_capital_allocation(ctx, exposure)
        risk_adjusted = build_risk_adjusted(metrics)
        correlation = build_correlation(ctx)
        scenario_risk = build_scenario_risk(ctx)
        stress = build_stress_loss(ctx, scenario_risk)
        tail = build_tail_risk(metrics)
        trends = build_risk_trends(ctx, metrics=metrics, drawdown=drawdown)
        alerts = build_alerts(
            drawdown=drawdown,
            concentration=concentration,
            exposure=exposure,
            capital=capital,
            tail=tail,
            metrics=metrics,
        )
        reports = build_reports(
            metrics=metrics,
            exposure=exposure,
            drawdown=drawdown,
            stress=stress,
            alerts=alerts,
            trends=trends,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "institutional_risk_analytics",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "metrics": metrics,
            "exposure": exposure,
            "drawdown": drawdown,
            "concentration": concentration,
            "capital_allocation": capital,
            "risk_adjusted": risk_adjusted,
            "correlation": correlation,
            "scenario_risk": scenario_risk,
            "stress_loss": stress,
            "tail_risk": tail,
            "trends": trends,
            "alerts": alerts,
            "reports": reports,
            "read_only": True,
            "never_modifies_production": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "daily",
                "weekly",
                "monthly",
                "quarterly",
                "portfolio_risk_report",
                "strategy_risk_report",
                "stress_risk_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"irap-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "risk_dashboard": {
                "metrics": pack["metrics"],
                "alerts": pack["alerts"],
            },
            "exposure_explorer": pack["exposure"],
            "drawdown_explorer": pack["drawdown"],
            "correlation_matrix": pack["correlation"],
            "stress_risk_explorer": pack["stress_loss"],
            "risk_reports": self.store.list_reports(limit=20),
            "tail_risk": pack["tail_risk"],
            "concentration": pack["concentration"],
        }
        return pack
