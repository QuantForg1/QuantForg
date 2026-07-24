"""ISLM platform — strategy lifecycle governance, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_strategy_lifecycle.analytics import (
    build_alerts,
    build_registry_from_sources,
    build_reports,
    build_timeline,
    merge_with_store,
    next_lifecycle_state,
)
from app.domain.institutional_strategy_lifecycle.gather import gather_lifecycle_sources
from app.domain.institutional_strategy_lifecycle.models import (
    ISOLATION_FLAGS,
    LIFECYCLE_ORDER,
    LifecycleState,
)
from app.domain.institutional_strategy_lifecycle.store import IslmStore


class InstitutionalStrategyLifecycleManager:
    def __init__(self, store: IslmStore | None = None) -> None:
        self.store = store or IslmStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def sync_registry(self, ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = ctx or gather_lifecycle_sources()
        derived = build_registry_from_sources(ctx)
        merged = merge_with_store(derived, self.store.list_strategies(limit=200))
        persisted: list[dict[str, Any]] = []
        for row in merged:
            persisted.append(self.store.upsert_strategy(row))
        return persisted

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_lifecycle_sources()
        strategies = self.sync_registry(ctx) if persist else merge_with_store(
            build_registry_from_sources(ctx),
            self.store.list_strategies(limit=200),
        )
        alerts = build_alerts(strategies, ctx)
        reports = build_reports(strategies=strategies, alerts=alerts)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "institutional_strategy_lifecycle",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "lifecycle_states": list(LIFECYCLE_ORDER),
            "registry": strategies,
            "alerts": alerts,
            "reports": reports,
            "approvals": self.store.list_approvals(limit=30),
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_changes_strategy_parameters": True,
            "never_approves_promotions_automatically": True,
            "never_retires_strategies_automatically": True,
            "human_approval_required_for_transitions": True,
        }
        if persist:
            for key in (
                "strategy_timeline",
                "version_history",
                "lifecycle_report",
                "health_report",
                "evidence_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"islm-{key}-{datetime.now(UTC).date()}",
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
            "lifecycle_timeline": build_timeline(primary)
            if primary
            else [{"stage": s, "status": "pending"} for s in LIFECYCLE_ORDER],
            "version_explorer": [
                {
                    "strategy_id": s.get("strategy_id"),
                    "version": s.get("version"),
                    "history": s.get("version_history"),
                }
                for s in pack["registry"]
            ],
            "health_dashboard": {
                "primary": primary.get("health"),
                "registry": [
                    {"strategy_id": s.get("strategy_id"), "health": s.get("health")}
                    for s in pack["registry"]
                ],
            },
            "evidence_viewer": primary.get("evidence"),
            "reports": self.store.list_reports(limit=20),
        }
        return pack

    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        self.sync_registry()
        row = self.store.get_strategy(strategy_id)
        if not row:
            return None
        return {
            **row,
            "timeline": build_timeline(row),
            "recommended_next_state": row.get("recommended_next_state")
            or next_lifecycle_state(str(row.get("lifecycle_state") or "")),
            "requires_human_approval_to_advance": True,
            "isolation": self.isolation,
        }

    def approve_transition(
        self,
        *,
        strategy_id: str,
        to_state: str,
        approver: str,
        decision: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Explicit human approval only — ISLM-isolated; never production."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        allowed = {s.value for s in LifecycleState}
        if to_state not in allowed:
            raise ValueError("invalid_lifecycle_state")
        row = self.store.get_strategy(strategy_id) or self.get_strategy(strategy_id)
        if not row:
            raise ValueError("strategy_not_found")
        from_state = str(row.get("lifecycle_state") or LifecycleState.DRAFT.value)
        entry = self.store.record_approval(
            strategy_id=strategy_id,
            from_state=from_state,
            to_state=to_state,
            approver=approver,
            decision=decision,
            comment=comment,
        )
        updated = self.store.get_strategy(strategy_id)
        return {
            "approval": entry,
            "strategy": updated,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "never_changes_strategy_parameters": True,
            "human_explicit": True,
            "isolation": self.isolation,
        }
