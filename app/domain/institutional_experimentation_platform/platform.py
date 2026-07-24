"""IEP platform — experiment governance, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_experimentation_platform.analytics import (
    build_comparison_workspace,
    build_decision_dashboard,
    build_hypothesis_builder,
    build_registry_from_sources,
    build_reports,
    statistical_consistency_check,
)
from app.domain.institutional_experimentation_platform.gather import (
    gather_experiment_sources,
)
from app.domain.institutional_experimentation_platform.models import (
    ISOLATION_FLAGS,
    LIFECYCLE_ORDER,
)
from app.domain.institutional_experimentation_platform.store import IepStore


class InstitutionalExperimentationPlatform:
    def __init__(self, store: IepStore | None = None) -> None:
        self.store = store or IepStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def sync_registry(self, ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = ctx or gather_experiment_sources()
        derived = build_registry_from_sources(ctx)
        persisted: list[dict[str, Any]] = []
        for row in derived:
            persisted.append(self.store.upsert_experiment(row))
        return persisted

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_experiment_sources()
        experiments = (
            self.sync_registry(ctx)
            if persist
            else build_registry_from_sources(ctx)
        )
        comparison = build_comparison_workspace(experiments)
        decisions = build_decision_dashboard(experiments)
        hypothesis = build_hypothesis_builder(experiments)
        reports = build_reports(
            experiments=experiments,
            comparison=comparison,
            decisions=decisions,
        )
        consistency = [
            {
                "experiment_id": e.get("experiment_id"),
                **statistical_consistency_check(e.get("statistics") or {}),
            }
            for e in experiments
            if e.get("statistics")
        ]
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "institutional_experimentation_platform",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "lifecycle_states": list(LIFECYCLE_ORDER),
            "registry": experiments,
            "comparison": comparison,
            "hypothesis_builder": hypothesis,
            "decision_dashboard": decisions,
            "statistical_consistency": consistency,
            "reports": reports,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "never_approves_experiments_automatically": True,
            "never_promotes_experiments_automatically": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "experiment_report",
                "comparison_report",
                "evidence_report",
                "decision_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"iep-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        primary = (pack.get("registry") or [None])[0] or {}
        pack["sections"] = {
            "experiment_registry": pack["registry"],
            "hypothesis_builder": pack["hypothesis_builder"],
            "comparison_workspace": pack["comparison"],
            "evidence_explorer": primary.get("evidence"),
            "decision_dashboard": pack["decision_dashboard"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        self.sync_registry()
        return self.store.get_experiment(experiment_id)
