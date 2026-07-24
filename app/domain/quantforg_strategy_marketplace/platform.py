"""QSMR platform — strategy marketplace registry, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_strategy_marketplace.analytics import (
    build_registry,
    build_reports,
    compare_strategies,
    discover,
    evidence_integrity_check,
    registry_consistency_check,
)
from app.domain.quantforg_strategy_marketplace.gather import gather_marketplace_sources
from app.domain.quantforg_strategy_marketplace.models import ISOLATION_FLAGS
from app.domain.quantforg_strategy_marketplace.store import QsmrStore


class QuantForgStrategyMarketplace:
    def __init__(self, store: QsmrStore | None = None) -> None:
        self.store = store or QsmrStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def sync_registry(self, ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = ctx or gather_marketplace_sources()
        derived = build_registry(ctx)
        persisted: list[dict[str, Any]] = []
        for row in derived:
            persisted.append(self.store.upsert_strategy(row))
        return persisted

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_marketplace_sources()
        registry = self.sync_registry(ctx) if persist else build_registry(ctx)
        discovery = discover(registry)
        comparison = compare_strategies(registry)
        reports = build_reports(registry)
        consistency = registry_consistency_check(registry)
        evidence_integrity = evidence_integrity_check(registry)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_strategy_marketplace",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "registry": registry,
            "discovery": discovery,
            "comparison": comparison,
            "reports": reports,
            "stats": {
                "strategy_count": len(registry),
                "active": sum(1 for r in registry if r.get("status") == "Active"),
                "research": sum(1 for r in registry if r.get("status") == "Research"),
                "retired": sum(
                    1 for r in registry if r.get("retirement_status") == "Retired"
                ),
            },
            "registry_consistency": consistency,
            "evidence_integrity": evidence_integrity,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_strategies": True,
            "never_modifies_production": True,
            "never_approves_certifications": True,
            "never_deploys_strategies": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "strategy_registry",
                "portfolio_summary",
                "certification_summary",
                "version_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qsmr-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        primary = (pack.get("registry") or [None])[0] or {}
        pack["sections"] = {
            "strategy_registry": pack["registry"],
            "strategy_explorer": pack["discovery"],
            "comparison_workspace": pack["comparison"],
            "evidence_viewer": {
                "strategy_id": primary.get("strategy_id"),
                "research_lineage": primary.get("research_lineage"),
                "replay_evidence": primary.get("replay_evidence"),
                "simulation_evidence": primary.get("simulation_evidence"),
                "validation_evidence": primary.get("validation_evidence"),
                "risk_profile": primary.get("risk_profile"),
                "deployment_history": primary.get("deployment_history"),
                "knowledge_graph_links": primary.get("knowledge_graph_links"),
            },
            "reports": self.store.list_reports(limit=20),
        }
        return pack

    def search(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        lifecycle: str | None = None,
        owner: str | None = None,
        certification_status: str | None = None,
        sort_by: str = "overall_strategy_score",
        sort_dir: str = "desc",
        group_by: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        registry = self.sync_registry()
        return discover(
            registry,
            q=q,
            status=status,
            lifecycle=lifecycle,
            owner=owner,
            certification_status=certification_status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            group_by=group_by,
            limit=limit,
        )

    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        self.sync_registry()
        return self.store.get_strategy(strategy_id)
