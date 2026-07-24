"""IRDP platform orchestrator — release governance, human approval only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_release_deployment.gather import gather_release_evidence
from app.domain.institutional_release_deployment.governance import (
    advance_stage,
    apply_human_approval,
    build_audit_record,
    build_checklist,
    build_pipeline_timeline,
    build_post_release_monitoring,
    build_reports,
    build_rollback_plan,
    draft_release,
)
from app.domain.institutional_release_deployment.models import (
    ISOLATION_FLAGS,
    PIPELINE_ORDER,
    ReleaseStatus,
)
from app.domain.institutional_release_deployment.store import IrdpStore


class InstitutionalReleaseDeploymentPlatform:
    def __init__(self, store: IrdpStore | None = None) -> None:
        self.store = store or IrdpStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def refresh_evidence(self) -> dict[str, Any]:
        ctx = gather_release_evidence()
        checklist = build_checklist(ctx)
        monitoring = build_post_release_monitoring(ctx)
        return {
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "checklist": checklist,
            "checklist_pass_count": sum(1 for c in checklist if c.get("passed")),
            "checklist_total": len(checklist),
            "monitoring": monitoring,
            "pipeline_stages": list(PIPELINE_ORDER),
        }

    def ensure_seed_release(self) -> dict[str, Any]:
        existing = self.store.list_releases(limit=1)
        if existing:
            return existing[0]
        row = draft_release(version="v3.0.0-rc1", component="QuantForg Enterprise")
        evidence = self.refresh_evidence()
        row["checklist"] = evidence["checklist"]
        row["evidence_links"] = {
            "cvf": "/cvf/dashboard",
            "eqs": "/eqs/dashboard",
            "res": "/res/dashboard",
            "ise": "/ise/dashboard",
            "qkg": "/qkg/dashboard",
        }
        return self.store.upsert_release(row)

    def dashboard(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        evidence = self.refresh_evidence()
        self.ensure_seed_release()
        releases = self.store.list_releases(limit=40)
        # Refresh checklist onto latest draft/in-progress releases
        for rel in releases[:5]:
            if rel.get("status") in {
                ReleaseStatus.DRAFT.value,
                ReleaseStatus.IN_PROGRESS.value,
                ReleaseStatus.AWAITING_APPROVAL.value,
            }:
                rel = {
                    **rel,
                    "checklist": evidence["checklist"],
                    "timeline": build_pipeline_timeline(rel),
                    "rollback_plan": rel.get("rollback_plan") or build_rollback_plan(rel),
                }
                self.store.upsert_release(rel)
        releases = self.store.list_releases(limit=40)
        approvals = self.store.list_approvals(limit=40)
        rollbacks = self.store.list_rollbacks(limit=40)
        reports = build_reports(
            releases=releases,
            approvals=approvals,
            rollbacks=rollbacks,
            monitoring=evidence["monitoring"],
        )
        for key, body in reports.items():
            if key == "generated_at" or not isinstance(body, dict):
                continue
            self.store.save_report(
                {
                    "report_id": f"irdp-{key}-{datetime.now(UTC).date()}",
                    "kind": key,
                    **body,
                }
            )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        awaiting = [
            r for r in releases if r.get("status") == ReleaseStatus.AWAITING_APPROVAL.value
        ]
        return {
            "schema_version": "1.0.0",
            "mode": "institutional_release_deployment",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": evidence["context"],
            "checklist": evidence["checklist"],
            "checklist_pass_count": evidence["checklist_pass_count"],
            "checklist_total": evidence["checklist_total"],
            "monitoring": evidence["monitoring"],
            "pipeline_stages": evidence["pipeline_stages"],
            "releases": releases,
            "awaiting_approval": awaiting,
            "approvals": approvals,
            "rollbacks": rollbacks,
            "reports": reports,
            "sections": {
                "release_dashboard": {
                    "release_count": len(releases),
                    "awaiting_approval": len(awaiting),
                    "health": evidence["monitoring"].get("release_health_score"),
                },
                "release_timeline": (releases[0].get("timeline") if releases else []),
                "approval_workspace": awaiting,
                "rollback_explorer": rollbacks,
                "release_reports": self.store.list_reports(limit=20),
            },
            "never_auto_approves": True,
            "never_executes_trades": True,
            "preserves_production_safety_guarantees": True,
        }

    def create_release(
        self, *, version: str, component: str = "QuantForg", notes: str | None = None
    ) -> dict[str, Any]:
        row = draft_release(version=version, component=component, notes=notes)
        evidence = self.refresh_evidence()
        row["checklist"] = evidence["checklist"]
        row["evidence_links"] = {
            "cvf": "/cvf/dashboard",
            "eqs": "/eqs/dashboard",
            "res": "/res/dashboard",
            "ise": "/ise/dashboard",
            "qkg": "/qkg/dashboard",
        }
        return self.store.upsert_release(row)

    def advance(self, release_id: str, *, to_stage: str | None = None) -> dict[str, Any] | None:
        row = self.store.get_release(release_id)
        if not row:
            return None
        updated = advance_stage(row, to_stage=to_stage)
        return self.store.upsert_release(updated)

    def approve(
        self,
        release_id: str,
        *,
        approver: str,
        decision: str,
        comment: str | None = None,
    ) -> dict[str, Any] | None:
        row = self.store.get_release(release_id)
        if not row:
            return None
        updated = apply_human_approval(
            row, approver=approver, decision=decision, comment=comment
        )
        saved = self.store.upsert_release(updated)
        self.store.record_approval(
            {
                "release_id": release_id,
                "version": saved.get("version"),
                "commit_hash": saved.get("commit_hash"),
                "approver": approver,
                "decision": decision,
                "comment": comment,
                "status": saved.get("status"),
            }
        )
        return saved

    def plan_rollback(
        self, release_id: str, *, requested_by: str, reason: str | None = None
    ) -> dict[str, Any] | None:
        row = self.store.get_release(release_id)
        if not row:
            return None
        plan = build_rollback_plan(row)
        plan["requested_by"] = requested_by
        plan["reason"] = reason
        plan["rollback_id"] = str(uuid4())
        # Record plan only — never execute rollback
        recorded = self.store.record_rollback(plan)
        updated = {
            **row,
            "rollback_plan": plan,
            "status": row.get("status"),
            "rollback_planned": True,
        }
        self.store.upsert_release(updated)
        return recorded

    def audit_pack(self, release_id: str) -> dict[str, Any] | None:
        row = self.store.get_release(release_id)
        if not row:
            return None
        return {
            "release": row,
            "audit": build_audit_record(row, event="release_audit_pack"),
            "approvals": [
                a
                for a in self.store.list_approvals(limit=100)
                if a.get("release_id") == release_id
            ],
            "rollbacks": [
                r
                for r in self.store.list_rollbacks(limit=100)
                if r.get("release_id") == release_id
            ],
            "never_auto_approves": True,
        }
