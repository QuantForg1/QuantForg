"""Unit tests — Institutional Release & Deployment Platform."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.institutional_release_deployment.governance import (
    advance_stage,
    apply_human_approval,
    build_checklist,
    build_post_release_monitoring,
    build_rollback_plan,
    draft_release,
)
from app.domain.institutional_release_deployment.models import (
    CHECKLIST_ITEMS,
    ISOLATION_FLAGS,
    PIPELINE_ORDER,
    ReleaseStage,
    ReleaseStatus,
)
from app.domain.institutional_release_deployment.platform import (
    InstitutionalReleaseDeploymentPlatform,
)
from app.domain.institutional_release_deployment.store import IrdpStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "cvf": {"confidence": {"confidence": 72}},
            "eqs": {"execution_score": {"overall_execution_score": 78, "latency": 80}},
            "res": {
                "reliability_score": {"overall_reliability_score": 81},
                "platform_health": {"overall_health": 81},
            },
            "ise": {
                "simulations": [{"simulation_id": "s1"}],
                "reports": [{"report_id": "r1"}],
            },
            "qkg": {"stats": {"node_count": 25}},
            "audit": [{"id": "a1"}],
            "icc": {"alerts": []},
            "prr": {"score": 90},
        },
        "availability": {
            "cvf": True,
            "eqs": True,
            "res": True,
            "ise": True,
            "qkg": True,
            "audit": True,
        },
    }


class TestIrdpGovernance:
    def test_checklist_and_monitoring(self) -> None:
        checklist = build_checklist(_ctx())
        assert len(checklist) >= len(CHECKLIST_ITEMS)
        assert all(c.get("never_auto_approves") for c in checklist)
        mon = build_post_release_monitoring(_ctx())
        assert 0 <= mon["release_health_score"] <= 100

    def test_human_approval_gate(self) -> None:
        rel = draft_release(version="v3.0.0-test", commit_hash="abc123")
        assert rel["human_approval_required"] is True
        # Advance toward staging without approval → blocked at human gate
        for _ in range(8):
            rel = advance_stage(rel)
            if rel.get("status") == ReleaseStatus.AWAITING_APPROVAL.value:
                break
        assert rel["stage"] == ReleaseStage.HUMAN_APPROVAL.value
        blocked = advance_stage(rel, to_stage=ReleaseStage.PRODUCTION.value)
        assert blocked.get("gate", {}).get("blocked") is True or blocked[
            "status"
        ] == ReleaseStatus.AWAITING_APPROVAL.value

        approved = apply_human_approval(
            rel, approver="alice", decision="approve", comment="ok"
        )
        assert approved["status"] == ReleaseStatus.APPROVED.value
        assert approved["approver"] == "alice"
        staged = advance_stage(approved, to_stage=ReleaseStage.STAGING.value)
        assert staged["status"] == ReleaseStatus.STAGED.value

    def test_rollback_never_automatic(self) -> None:
        rel = draft_release(version="v3.0.0-rb", commit_hash="def")
        plan = build_rollback_plan(rel)
        assert plan["never_rollback_automatically"] is True
        assert plan["automatic"] is False


class TestIrdpPlatform:
    def test_workflow_and_audit_integrity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert ISOLATION_FLAGS["approves_releases_automatically"] is False
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["rollbacks_automatically"] is False
        irdp = InstitutionalReleaseDeploymentPlatform(
            store=IrdpStore(path=tmp_path / "irdp.json")
        )
        monkeypatch.setattr(
            "app.domain.institutional_release_deployment.platform.gather_release_evidence",
            _ctx,
        )
        t0 = time.perf_counter()
        created = irdp.create_release(version="v3.1.0")
        assert created["release_id"]
        # Move to approval
        row = created
        for _ in range(10):
            row = irdp.advance(row["release_id"]) or row
            if row.get("status") == ReleaseStatus.AWAITING_APPROVAL.value:
                break
        approved = irdp.approve(
            row["release_id"], approver="bob", decision="approve"
        )
        assert approved and approved["status"] == ReleaseStatus.APPROVED.value
        approvals = irdp.store.list_approvals(limit=5)
        assert approvals
        assert approvals[0]["automatic"] is False
        rb = irdp.plan_rollback(row["release_id"], requested_by="bob")
        assert rb and rb["never_rollback_automatically"] is True
        audit = irdp.audit_pack(row["release_id"])
        assert audit and audit["audit"]["release_id"] == row["release_id"]
        assert audit["audit"]["commit_hash"]
        dash = irdp.dashboard()
        assert dash["never_auto_approves"] is True
        assert set(PIPELINE_ORDER).issubset(set(dash["pipeline_stages"]))
        assert time.perf_counter() - t0 < 45
