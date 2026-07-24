"""QSF platform — governed strategy factory workflow (isolated)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_strategy_factory.analytics import (
    build_approval_queue,
    build_dossiers,
    build_pipeline_board,
    build_reports,
    build_work_items,
    can_transition,
    evidence_integrity_check,
    next_stage,
    workflow_consistency_check,
)
from app.domain.quantforg_strategy_factory.gather import gather_factory_sources
from app.domain.quantforg_strategy_factory.models import (
    ISOLATION_FLAGS,
    PIPELINE_STAGES,
)
from app.domain.quantforg_strategy_factory.store import QsfStore


class QuantForgStrategyFactory:
    def __init__(self, store: QsfStore | None = None) -> None:
        self.store = store or QsfStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_factory_sources()
        overrides = self.store.get_stage_overrides()
        work_items = build_work_items(ctx, stage_overrides=overrides)
        board = build_pipeline_board(work_items)
        dossiers = build_dossiers(ctx, work_items)
        approvals = self.store.list_approvals(limit=50)
        queue = build_approval_queue(work_items, approvals)
        reports = build_reports(
            board=board, work_items=work_items, dossiers=dossiers, queue=queue
        )
        workflow_consistency = workflow_consistency_check(work_items, queue)
        evidence_integrity = evidence_integrity_check(work_items, dossiers)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_strategy_factory",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "pipeline_stages": list(PIPELINE_STAGES),
            "work_items": work_items,
            "pipeline_board": board,
            "dossiers": dossiers,
            "approval_queue": queue,
            "approvals": approvals,
            "reports": reports,
            "workflow_consistency": workflow_consistency,
            "evidence_integrity": evidence_integrity,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_approves_releases": True,
            "never_deploys_strategies": True,
            "never_allocates_capital": True,
            "human_approval_required_for_transitions": True,
            "preserves_existing_safety_guarantees": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "factory_status_report",
                "pipeline_progress_report",
                "dossier_index",
                "approval_queue_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qsf-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "factory_dashboard": {
                "stage_counts": (pack.get("pipeline_board") or {}).get("counts"),
                "work_item_count": len(pack.get("work_items") or []),
                "queue_depth": len(pack.get("approval_queue") or []),
            },
            "pipeline_board": pack["pipeline_board"],
            "strategy_workspace": pack["work_items"],
            "evidence_center": {
                "dossiers": (pack.get("dossiers") or {}).get("dossiers"),
                "availability": (pack.get("context") or {}).get("availability"),
            },
            "approval_queue": pack["approval_queue"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack

    def approve_transition(
        self,
        *,
        strategy_id: str,
        to_stage: str,
        approver: str,
        decision: str,
        comment: str | None = None,
        work_item_id: str | None = None,
    ) -> dict[str, Any]:
        """Explicit human approval — QSF isolation only; never production/deploy."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if to_stage not in PIPELINE_STAGES:
            raise ValueError("invalid_pipeline_stage")
        pack = self.run(persist=False)
        item = next(
            (
                w
                for w in pack.get("work_items") or []
                if w.get("strategy_id") == strategy_id
            ),
            None,
        )
        if not item:
            raise ValueError("strategy_work_item_not_found")
        from_stage = str(item.get("pipeline_stage"))
        expected = next_stage(from_stage)
        if decision == "approved":
            if to_stage != expected:
                raise ValueError("to_stage_must_be_next_pipeline_step")
            if not can_transition(from_stage, to_stage):
                raise ValueError("invalid_transition")
        entry = self.store.record_approval(
            strategy_id=strategy_id,
            from_stage=from_stage,
            to_stage=to_stage if decision == "approved" else from_stage,
            approver=approver,
            decision=decision,
            comment=comment,
            work_item_id=work_item_id or str(item.get("work_item_id")),
        )
        refreshed = self.run(persist=True)
        updated = next(
            (
                w
                for w in refreshed.get("work_items") or []
                if w.get("strategy_id") == strategy_id
            ),
            None,
        )
        return {
            "approval": entry,
            "work_item": updated,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "never_deploys_strategies": True,
            "never_approves_releases": True,
            "never_allocates_capital": True,
            "human_explicit": True,
            "isolation": self.isolation,
        }
