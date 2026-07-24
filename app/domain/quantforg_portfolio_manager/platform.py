"""QPM platform — portfolio orchestration, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_portfolio_manager.analytics import (
    build_capital_allocation,
    build_capacity_analysis,
    build_correlation_analysis,
    build_diversification_analysis,
    build_metrics,
    build_portfolio_exposure,
    build_portfolio_health,
    build_portfolio_readiness,
    build_recommendations,
    build_reports,
    build_strategy_ranking,
    evidence_integrity_check,
    recommendation_consistency_check,
)
from app.domain.quantforg_portfolio_manager.gather import gather_portfolio_sources
from app.domain.quantforg_portfolio_manager.models import ISOLATION_FLAGS
from app.domain.quantforg_portfolio_manager.store import QpmStore


class QuantForgPortfolioManager:
    def __init__(self, store: QpmStore | None = None) -> None:
        self.store = store or QpmStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_portfolio_sources()
        ranking = build_strategy_ranking(ctx)
        allocation = build_capital_allocation(ranking)
        exposure = build_portfolio_exposure(ranking, allocation)
        capacity = build_capacity_analysis(ranking, ctx)
        correlation = build_correlation_analysis(ranking)
        diversification = build_diversification_analysis(exposure, correlation)
        metrics = build_metrics(
            ctx,
            ranked=ranking,
            allocation=allocation,
            diversification=diversification,
            correlation=correlation,
            capacity=capacity,
        )
        health = build_portfolio_health(metrics, ranking)
        readiness = build_portfolio_readiness(ctx, health, ranking)
        recommendations = build_recommendations(ranking, metrics, allocation)
        reports = build_reports(
            allocation=allocation,
            ranked=ranking,
            exposure=exposure,
            diversification=diversification,
            metrics=metrics,
            recommendations=recommendations,
            health=health,
            readiness=readiness,
        )
        rec_consistency = recommendation_consistency_check(recommendations)
        evidence_integrity = evidence_integrity_check(
            ranked=ranking, allocation=allocation, metrics=metrics
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_portfolio_manager",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "capital_allocation": allocation,
            "portfolio_exposure": exposure,
            "strategy_ranking": ranking,
            "capacity_analysis": capacity,
            "correlation_analysis": correlation,
            "diversification_analysis": diversification,
            "portfolio_health": health,
            "portfolio_readiness": readiness,
            "metrics": metrics,
            "recommendations": recommendations,
            "reports": reports,
            "recommendation_consistency": rec_consistency,
            "evidence_integrity": evidence_integrity,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_changes_strategy_parameters": True,
            "never_rebalances_automatically": True,
            "never_allocates_capital_automatically": True,
            "human_approval_required_for_actions": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "portfolio_allocation_report",
                "strategy_ranking_report",
                "exposure_report",
                "diversification_report",
                "executive_portfolio_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qpm-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "portfolio_dashboard": {
                "metrics": pack["metrics"],
                "health": pack["portfolio_health"],
                "readiness": pack["portfolio_readiness"],
                "recommendations": pack["recommendations"][:10],
            },
            "allocation_explorer": pack["capital_allocation"],
            "strategy_ranking": pack["strategy_ranking"],
            "diversification_matrix": {
                "diversification": pack["diversification_analysis"],
                "correlation": pack["correlation_analysis"],
                "exposure": pack["portfolio_exposure"],
            },
            "portfolio_reports": self.store.list_reports(limit=20),
        }
        return pack
