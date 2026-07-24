"""QPTCM platform — paper trading campaign orchestration (isolated)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_paper_trading_campaign.analytics import (
    build_campaigns,
    build_daily_timeline,
    build_graduation_workspace,
    build_reports,
    can_transition,
    evidence_integrity_check,
    next_lifecycle,
    workflow_consistency_check,
)
from app.domain.quantforg_paper_trading_campaign.gather import gather_campaign_sources
from app.domain.quantforg_paper_trading_campaign.models import (
    CAMPAIGN_LIFECYCLE,
    CampaignLifecycle,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_paper_trading_campaign.store import QptcmStore


class QuantForgPaperTradingCampaignManager:
    def __init__(self, store: QptcmStore | None = None) -> None:
        self.store = store or QptcmStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_campaign_sources()
        overrides = self.store.get_lifecycle_overrides()
        campaigns = build_campaigns(ctx, lifecycle_overrides=overrides)
        timeline = build_daily_timeline(campaigns)
        graduation = build_graduation_workspace(campaigns)
        reports = build_reports(campaigns)
        approvals = self.store.list_approvals(limit=50)
        workflow_consistency = workflow_consistency_check(campaigns)
        evidence_integrity = evidence_integrity_check(campaigns)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_paper_trading_campaign",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "lifecycle_stages": list(CAMPAIGN_LIFECYCLE),
            "campaigns": campaigns,
            "daily_timeline": timeline,
            "graduation_workspace": graduation,
            "reports": reports,
            "approvals": approvals,
            "workflow_consistency": workflow_consistency,
            "evidence_integrity": evidence_integrity,
            "read_only": True,
            "paper_trading_only": True,
            "never_places_live_trades": True,
            "never_modifies_production": True,
            "never_allocates_capital": True,
            "never_approves_graduation_automatically": True,
            "human_approval_required_for_transitions": True,
            "preserves_existing_safety_guarantees": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "daily_campaign_report",
                "weekly_campaign_report",
                "final_evaluation",
                "graduation_report",
                "lessons_learned",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qptcm-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        counts = {s: 0 for s in CAMPAIGN_LIFECYCLE}
        for c in pack.get("campaigns") or []:
            lc = str(c.get("lifecycle") or "")
            if lc in counts:
                counts[lc] += 1
        pack["sections"] = {
            "campaign_dashboard": {
                "campaign_count": len(pack.get("campaigns") or []),
                "lifecycle_counts": counts,
                "graduation_candidates": len(
                    (pack.get("graduation_workspace") or {}).get("candidates") or []
                ),
            },
            "campaign_explorer": pack["campaigns"],
            "daily_timeline": pack["daily_timeline"],
            "evidence_center": {
                "campaigns": [
                    {
                        "campaign_id": c.get("campaign_id"),
                        "evidence": c.get("evidence"),
                        "incidents": c.get("incidents"),
                        "recommendations": c.get("recommendations"),
                    }
                    for c in pack.get("campaigns") or []
                ]
            },
            "graduation_workspace": pack["graduation_workspace"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack

    def approve_transition(
        self,
        *,
        campaign_id: str,
        to_state: str,
        approver: str,
        decision: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Explicit human approval — QPTCM isolation; never live / capital / auto-grad."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if to_state not in CAMPAIGN_LIFECYCLE:
            raise ValueError("invalid_campaign_lifecycle")
        pack = self.run(persist=False)
        campaign = next(
            (
                c
                for c in pack.get("campaigns") or []
                if c.get("campaign_id") == campaign_id
            ),
            None,
        )
        if not campaign:
            raise ValueError("campaign_not_found")
        from_state = str(campaign.get("lifecycle"))
        expected = next_lifecycle(from_state)
        if decision == "approved":
            if to_state != expected:
                raise ValueError("to_state_must_be_next_lifecycle_step")
            if not can_transition(from_state, to_state):
                raise ValueError("invalid_transition")
            # Graduation Candidate still never means live authorization
            if to_state == CampaignLifecycle.GRADUATION_CANDIDATE.value:
                comment = (comment or "") + " | graduation_candidate_not_live_auth"
        entry = self.store.record_approval(
            campaign_id=campaign_id,
            from_state=from_state,
            to_state=to_state if decision == "approved" else from_state,
            approver=approver,
            decision=decision,
            comment=comment,
        )
        refreshed = self.run(persist=True)
        updated = next(
            (
                c
                for c in refreshed.get("campaigns") or []
                if c.get("campaign_id") == campaign_id
            ),
            None,
        )
        return {
            "approval": entry,
            "campaign": updated,
            "never_places_live_trades": True,
            "never_modifies_production": True,
            "never_allocates_capital": True,
            "never_approves_graduation_automatically": True,
            "human_explicit": True,
            "live_deployment_blocked": True,
            "isolation": self.isolation,
        }
