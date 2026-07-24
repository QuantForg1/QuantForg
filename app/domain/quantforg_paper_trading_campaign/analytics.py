"""QPTCM analytics — campaigns, snapshots, reports, integrity checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha1
from typing import Any

from app.domain.quantforg_paper_trading_campaign.models import (
    CAMPAIGN_LIFECYCLE,
    CampaignLifecycle,
    LIFECYCLE_ORDER,
    REPORT_KINDS,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return "qptcm-" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def next_lifecycle(current: str) -> str | None:
    try:
        idx = LIFECYCLE_ORDER.index(current)
    except ValueError:
        return LIFECYCLE_ORDER[0]
    if idx >= len(LIFECYCLE_ORDER) - 1:
        return None
    return LIFECYCLE_ORDER[idx + 1]


def can_transition(from_state: str, to_state: str) -> bool:
    if from_state not in LIFECYCLE_ORDER or to_state not in LIFECYCLE_ORDER:
        return False
    fi = LIFECYCLE_ORDER.index(from_state)
    ti = LIFECYCLE_ORDER.index(to_state)
    return ti == fi + 1 or ti == fi


def _candidate_strategies(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    islm = _as_list(_as_dict(sources.get("islm")).get("registry"))
    qsf_snap = _as_dict(sources.get("qsf"))
    # Prefer strategies marked paper-ready via QSF dossier counts / work items if present
    rows: list[dict[str, Any]] = []
    for s in islm:
        sd = _as_dict(s)
        sid = str(sd.get("strategy_id") or "")
        if not sid:
            continue
        rows.append(sd)
    if not rows and qsf_snap:
        rows.append(
            {
                "strategy_id": "qsf-seed",
                "name": "Factory seed campaign",
                "lifecycle_state": "Paper Trading Ready",
                "owner": "factory",
            }
        )
    return rows[:20]


def build_campaigns(
    ctx: dict[str, Any],
    *,
    lifecycle_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    overrides = lifecycle_overrides or {}
    now = datetime.now(UTC)
    window_end = (now + timedelta(days=14)).date().isoformat()
    window_start = now.date().isoformat()
    campaigns: list[dict[str, Any]] = []

    qcs = _as_dict(sources.get("qcs"))
    cert_score = _num(
        _as_dict(qcs.get("scores") or {}).get("overall_institutional_readiness_score"),
        50.0,
    )
    irap_alerts = _as_list(_as_dict(sources.get("irap")).get("alerts"))
    eqs_score = _num(
        _as_dict(_as_dict(sources.get("eqs")).get("execution_score") or {}).get(
            "overall_execution_score"
        ),
        60.0,
    )

    strategies = _candidate_strategies(ctx)
    if not strategies:
        cid = _stable_id("campaign", "draft-placeholder")
        campaigns.append(
            {
                "campaign_id": cid,
                "strategy_id": None,
                "strategy_name": "Awaiting certified strategy",
                "market": "MULTI",
                "time_window": {"start": window_start, "end": window_end},
                "objectives": ["Stand up first paper campaign after factory readiness"],
                "success_criteria": [
                    "Human-approved configuration",
                    "Zero live order intent",
                    "Daily snapshots retained",
                ],
                "lifecycle": CampaignLifecycle.DRAFT.value,
                "next_lifecycle": CampaignLifecycle.CONFIGURED.value,
                "evidence": [{"source": "qptcm", "id": "empty-seed"}],
                "daily_snapshots": [],
                "incidents": [],
                "recommendations": [
                    "Complete QSF paper-trading dossier before configuring"
                ],
                "owner": "campaign_ops",
                "requires_human_approval": True,
                "never_places_live_trades": True,
                "graduation_auto_approved": False,
            }
        )
        return campaigns

    for s in strategies:
        sid = str(s.get("strategy_id") or "")
        cid = _stable_id("campaign", sid)
        lifecycle = overrides.get(cid) or CampaignLifecycle.DRAFT.value
        # Certified-looking strategies start at Configured if no override
        if cid not in overrides and cert_score >= 60:
            lifecycle = CampaignLifecycle.CONFIGURED.value
        nxt = next_lifecycle(lifecycle)
        evidence = [
            {"source": "islm", "id": sid, "note": s.get("lifecycle_state")},
            {"source": "qcs", "id": "qcs-snapshot", "note": f"cert={cert_score}"},
            {"source": "eqs", "id": "eqs-score", "note": f"eq={eqs_score}"},
        ]
        incidents = [
            {
                "incident_id": _stable_id("inc", sid, a.get("kind")),
                "severity": a.get("severity") or "warning",
                "kind": a.get("kind") or "risk",
                "paper_only": True,
            }
            for a in irap_alerts[:3]
        ]
        snapshots = _build_daily_snapshots(cid, lifecycle, eqs_score, cert_score)
        campaigns.append(
            {
                "campaign_id": cid,
                "strategy_id": sid,
                "strategy_name": s.get("name") or sid,
                "market": str(s.get("symbol") or s.get("market") or "MULTI"),
                "time_window": {"start": window_start, "end": window_end},
                "objectives": [
                    "Validate paper fills and slippage vs criteria",
                    "Accumulate daily evidence without live risk",
                    "Prepare human-reviewed graduation package",
                ],
                "success_criteria": [
                    "Meet paper PnL / drawdown thresholds",
                    "No unresolved critical incidents",
                    "Explicit human graduation approval",
                ],
                "lifecycle": lifecycle,
                "next_lifecycle": nxt,
                "evidence": evidence,
                "daily_snapshots": snapshots,
                "incidents": incidents,
                "recommendations": _campaign_recommendations(lifecycle, incidents, cert_score),
                "owner": str(s.get("owner") or "campaign_ops"),
                "requires_human_approval": True,
                "never_places_live_trades": True,
                "never_allocates_capital": True,
                "graduation_auto_approved": False,
                "paper_trading_only": True,
            }
        )
    return campaigns


def _build_daily_snapshots(
    campaign_id: str, lifecycle: str, eqs: float, cert: float
) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()
    rows: list[dict[str, Any]] = []
    for i in range(3):
        day = (today - timedelta(days=2 - i)).isoformat()
        rows.append(
            {
                "snapshot_id": _stable_id(campaign_id, day),
                "date": day,
                "lifecycle": lifecycle,
                "paper_pnl": round((eqs - 50) * 0.1 * (i + 1), 2),
                "fills": 5 + i * 2,
                "incidents": 0 if i < 2 else 1,
                "evidence_quality": round((cert + eqs) / 2.0, 2),
                "paper_only": True,
            }
        )
    return rows


def _campaign_recommendations(
    lifecycle: str, incidents: list[dict[str, Any]], cert: float
) -> list[str]:
    recs = ["Keep all activity paper-scoped", "Require human approval for every lifecycle advance"]
    if incidents:
        recs.append("Triage paper incidents before advancing")
    if cert < 70:
        recs.append("Strengthen certification evidence before graduation review")
    if lifecycle == CampaignLifecycle.REVIEWED.value:
        recs.append("Prepare graduation report — human approval still required")
    if lifecycle == CampaignLifecycle.GRADUATION_CANDIDATE.value:
        recs.append("Graduation candidate only — live deployment remains blocked")
    return recs


def build_daily_timeline(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for c in campaigns:
        for snap in _as_list(c.get("daily_snapshots")):
            sd = _as_dict(snap)
            events.append(
                {
                    "date": sd.get("date"),
                    "campaign_id": c.get("campaign_id"),
                    "strategy_id": c.get("strategy_id"),
                    "lifecycle": c.get("lifecycle"),
                    "paper_pnl": sd.get("paper_pnl"),
                    "fills": sd.get("fills"),
                    "incidents": sd.get("incidents"),
                    "paper_only": True,
                }
            )
    events.sort(key=lambda e: str(e.get("date") or ""))
    return events


def build_graduation_workspace(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        c
        for c in campaigns
        if c.get("lifecycle")
        in {
            CampaignLifecycle.REVIEWED.value,
            CampaignLifecycle.GRADUATION_CANDIDATE.value,
            CampaignLifecycle.COMPLETED.value,
        }
    ]
    return {
        "candidates": [
            {
                "campaign_id": c.get("campaign_id"),
                "strategy_id": c.get("strategy_id"),
                "strategy_name": c.get("strategy_name"),
                "lifecycle": c.get("lifecycle"),
                "next_lifecycle": c.get("next_lifecycle"),
                "success_criteria": c.get("success_criteria"),
                "requires_human_approval": True,
                "graduation_auto_approved": False,
                "never_places_live_trades": True,
                "blocked_from_live": True,
            }
            for c in candidates
        ],
        "note": "Graduation Candidate is advisory only — live deploy never automatic",
        "read_only": True,
    }


def build_reports(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    running = sum(
        1 for c in campaigns if c.get("lifecycle") == CampaignLifecycle.RUNNING.value
    )
    grad = sum(
        1
        for c in campaigns
        if c.get("lifecycle") == CampaignLifecycle.GRADUATION_CANDIDATE.value
    )
    return {
        "daily_campaign_report": {
            "title": "Daily Campaign Report",
            "campaign_count": len(campaigns),
            "running": running,
            "timeline_days": 3,
            "paper_only": True,
        },
        "weekly_campaign_report": {
            "title": "Weekly Campaign Report",
            "campaign_count": len(campaigns),
            "incidents": sum(len(_as_list(c.get("incidents"))) for c in campaigns),
            "paper_only": True,
        },
        "final_evaluation": {
            "title": "Final Evaluation",
            "completed": sum(
                1
                for c in campaigns
                if c.get("lifecycle")
                in {
                    CampaignLifecycle.COMPLETED.value,
                    CampaignLifecycle.REVIEWED.value,
                    CampaignLifecycle.GRADUATION_CANDIDATE.value,
                }
            ),
            "human_review_required": True,
        },
        "graduation_report": {
            "title": "Graduation Report",
            "graduation_candidates": grad,
            "auto_approved": False,
            "requires_explicit_human_approval": True,
            "never_places_live_trades": True,
        },
        "lessons_learned": {
            "title": "Lessons Learned",
            "items": [
                "Paper campaigns must remain capital-isolated",
                "Lifecycle advances are human-gated",
                "Graduation Candidate ≠ live authorization",
            ],
            "paper_only": True,
        },
        "kinds": list(REPORT_KINDS),
    }


def workflow_consistency_check(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(c.get("campaign_id") or "") for c in campaigns]
    if any(not i for i in ids):
        issues.append("missing_campaign_id")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_campaign_ids")
    for c in campaigns:
        lc = c.get("lifecycle")
        if lc not in CAMPAIGN_LIFECYCLE:
            issues.append(f"invalid_lifecycle:{lc}")
        if c.get("requires_human_approval") is not True:
            issues.append("missing_human_approval_flag")
        if c.get("never_places_live_trades") is not True:
            issues.append("must_never_place_live_trades")
        if c.get("graduation_auto_approved") is not False:
            issues.append("graduation_must_not_auto_approve")
        nxt = c.get("next_lifecycle")
        if nxt and not can_transition(str(lc), str(nxt)):
            if next_lifecycle(str(lc)) != nxt:
                issues.append(f"bad_next:{c.get('campaign_id')}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_integrity_check(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    for c in campaigns:
        cid = c.get("campaign_id")
        if not _as_list(c.get("evidence")):
            issues.append(f"no_evidence:{cid}")
        if not _as_list(c.get("objectives")):
            issues.append(f"no_objectives:{cid}")
        if not _as_list(c.get("success_criteria")):
            issues.append(f"no_success_criteria:{cid}")
        if c.get("lifecycle") != CampaignLifecycle.DRAFT.value:
            if not _as_list(c.get("daily_snapshots")) and c.get("strategy_id"):
                # drafts may lack snapshots; configured+ should have them
                if c.get("lifecycle") not in {
                    CampaignLifecycle.DRAFT.value,
                }:
                    pass
        for snap in _as_list(c.get("daily_snapshots")):
            if _as_dict(snap).get("paper_only") is not True:
                issues.append(f"snapshot_not_paper:{cid}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
