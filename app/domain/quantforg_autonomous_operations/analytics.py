"""AOC analytics — health, recommendations, queue, scores, reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.quantforg_autonomous_operations.models import (
    DATA_SOURCES,
    EXECUTIVE_SCORE_KEYS,
    QUEUE_PRIORITIES,
    RECOMMENDATION_KINDS,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(max(lo, min(hi, n)), 1)


def _score_or(default: float, *candidates: Any) -> float:
    for c in candidates:
        v = _f(c)
        if v is not None:
            if 0.0 < v <= 1.0:
                return _clamp(v * 100.0)
            return _clamp(v)
    return _clamp(default)


def build_operational_health(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    availability = _as_dict(ctx.get("availability"))
    icp = _as_dict(sources.get("icp"))
    icp_health = _as_dict(icp.get("health") or icp)
    eqs = _as_dict(sources.get("eqs"))
    res = _as_dict(sources.get("res"))
    cvf = _as_dict(sources.get("cvf"))
    missing = [s for s in DATA_SOURCES if not availability.get(s)]
    overall = _score_or(
        50.0,
        icp_health.get("overall_platform_health"),
        (
            _score_or(50.0, _as_dict(eqs.get("execution_score") or eqs).get("overall_execution_score"))
            + _score_or(
                50.0,
                _as_dict(res.get("reliability_score") or res).get(
                    "overall_reliability_score"
                ),
            )
            + _score_or(
                50.0,
                _as_dict(cvf.get("confidence") or cvf).get("confidence"),
            )
        )
        / 3.0,
    )
    return {
        "overall_operational_health": overall,
        "source_count": ctx.get("source_count"),
        "missing_sources": missing,
        "execution_score": _score_or(
            50.0,
            _as_dict(eqs.get("execution_score") or eqs).get("overall_execution_score"),
        ),
        "reliability_score": _score_or(
            50.0,
            _as_dict(res.get("reliability_score") or res).get(
                "overall_reliability_score"
            ),
        ),
        "validation_confidence": _score_or(
            50.0, _as_dict(cvf.get("confidence") or cvf).get("confidence")
        ),
        "read_only": True,
    }


def build_watch_modules(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    irap = _as_dict(sources.get("irap"))
    cvf = _as_dict(sources.get("cvf"))
    qpm = _as_dict(sources.get("qpm"))
    qcs = _as_dict(sources.get("qcs"))
    iep = _as_dict(sources.get("iep"))
    islm = _as_dict(sources.get("islm"))
    eqs = _as_dict(sources.get("eqs"))
    res = _as_dict(sources.get("res"))

    return {
        "risk_watch": {
            "alerts": _as_list(irap.get("alerts"))[:10],
            "metrics": _as_dict(irap.get("metrics") or irap),
            "drawdown": _f(
                _as_dict(irap.get("metrics") or irap).get("maximum_drawdown")
            ),
        },
        "validation_watch": {
            "confidence": _as_dict(cvf.get("confidence") or cvf).get("confidence"),
            "alerts": _as_list(cvf.get("alerts"))[:10],
        },
        "portfolio_watch": {
            "metrics": _as_dict(qpm.get("metrics") or qpm),
            "health": _as_dict(qpm.get("health") or qpm.get("portfolio_health")),
            "recommendations": _as_list(qpm.get("recommendations"))[:10],
        },
        "release_readiness": {
            "certification_level": _as_dict(qcs.get("level") or qcs).get("level"),
            "blockers": _as_list(qcs.get("blockers"))[:10],
            "overall": _as_dict(qcs.get("scores") or qcs).get(
                "overall_institutional_readiness_score"
            ),
        },
        "research_backlog": {
            "experiments": _as_list(iep.get("registry"))[:15],
            "strategies": _as_list(islm.get("registry"))[:15],
            "aqs_recommendations": _as_list(
                _as_dict(sources.get("aqs")).get("recommendations")
            )[:15],
        },
        "incident_prioritization": {
            "eqs_alerts": _as_list(eqs.get("alerts"))[:10],
            "res_alerts": _as_list(res.get("alerts"))[:10],
            "icp_alerts": _as_list(_as_dict(sources.get("icp")).get("alerts"))[:10],
        },
    }


def build_recommendations(ctx: dict[str, Any], watches: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    recs: list[dict[str, Any]] = []

    def add(
        kind: str,
        *,
        category: str,
        detail: str,
        evidence: dict[str, Any],
        owner: str = "ops-desk",
        priority: str = "P2",
        dependencies: list[str] | None = None,
        next_action: str | None = None,
    ) -> None:
        if kind not in RECOMMENDATION_KINDS:
            kind = "Research candidate"
        recs.append(
            {
                "recommendation_id": str(uuid4()),
                "kind": kind,
                "category": category,
                "detail": detail,
                "owner": owner,
                "priority": priority if priority in QUEUE_PRIORITIES else "P2",
                "dependencies": dependencies or [],
                "suggested_next_action": next_action or f"Review and approve: {kind}",
                "evidence": evidence,
                "requires_human_approval": True,
                "auto_applied": False,
                "never_remediates_automatically": True,
                "read_only": True,
            }
        )

    conf = _f(_as_dict(watches.get("validation_watch")).get("confidence"))
    if conf is not None and conf < 50:
        add(
            "Validation required",
            category="Validation Watch",
            detail=f"CVF confidence {conf}",
            evidence={"confidence": conf, "alerts": _as_dict(watches.get("validation_watch")).get("alerts")},
            priority="P1" if conf < 40 else "P2",
            dependencies=["cvf"],
            next_action="Open CVF and request human validation review",
        )

    dd = _f(_as_dict(watches.get("risk_watch")).get("drawdown"))
    if dd is not None and dd >= 20:
        add(
            "Risk review required",
            category="Risk Watch",
            detail=f"IRAP drawdown {dd}",
            evidence={"drawdown": dd, "alerts": _as_dict(watches.get("risk_watch")).get("alerts")},
            priority="P0" if dd >= 30 else "P1",
            dependencies=["irap"],
            next_action="Open IRAP and escalate risk review",
        )

    qcs_level = str(
        _as_dict(watches.get("release_readiness")).get("certification_level") or ""
    ).lower()
    blockers = _as_list(_as_dict(watches.get("release_readiness")).get("blockers"))
    if blockers or "not ready" in qcs_level:
        add(
            "Certification required",
            category="Release Readiness",
            detail=f"QCS level={qcs_level or 'unknown'} blockers={len(blockers)}",
            evidence={"level": qcs_level, "blockers": blockers[:5]},
            priority="P1",
            dependencies=["qcs"],
            next_action="Run QCS readiness review with human certification approval",
        )
    elif "staging" in qcs_level or "production" in qcs_level:
        add(
            "Release candidate",
            category="Release Readiness",
            detail=f"Certification level suggests release path: {qcs_level}",
            evidence={"level": qcs_level},
            priority="P2",
            dependencies=["qcs", "irdp"],
            next_action="Prepare IRDP release package for explicit human approval",
        )

    sims = _as_list(_as_dict(sources.get("ise")).get("simulations"))
    if len(sims) < 1:
        add(
            "Simulation recommended",
            category="Research Backlog",
            detail="No recent ISE simulations in snapshot",
            evidence={"simulation_count": 0},
            priority="P2",
            dependencies=["ise"],
            next_action="Queue digital-twin simulation in ISE (research only)",
        )

    replay_n = sum(
        1
        for s in sims
        if isinstance(s, dict)
        and (
            "replay" in str(s.get("mode") or "").lower()
            or "historical" in str(s.get("mode") or s.get("scenario") or "").lower()
        )
    )
    if sims and replay_n < 1:
        add(
            "Replay recommended",
            category="Research Backlog",
            detail="Simulations present but no replay/historical modes",
            evidence={"simulation_count": len(sims), "replay_count": replay_n},
            priority="P2",
            dependencies=["ise", "irl"],
            next_action="Schedule historical replay validation",
        )

    for exp in _as_list(_as_dict(watches.get("research_backlog")).get("experiments"))[:5]:
        ed = _as_dict(exp)
        state = str(ed.get("lifecycle_state") or ed.get("status") or "").lower()
        if "human" in state or "ai review" in state or "research" in state or not state:
            add(
                "Research candidate",
                category="Research Backlog",
                detail=f"Experiment {ed.get('experiment_id') or ed.get('title')}",
                evidence=ed,
                priority="P2",
                owner="research-desk",
                dependencies=["iep"],
                next_action="Review experiment evidence in IEP",
            )

    for aqs in _as_list(
        _as_dict(watches.get("research_backlog")).get("aqs_recommendations")
    )[:3]:
        ad = _as_dict(aqs)
        add(
            "Research candidate",
            category="Research Backlog",
            detail=str(ad.get("title") or ad.get("summary") or "AQS recommendation"),
            evidence=ad,
            priority="P3",
            owner="research-desk",
            dependencies=["aqs"],
            next_action="Triage AQS recommendation (advisory only)",
        )

    if not _as_dict(sources.get("qkg")):
        add(
            "Documentation update required",
            category="Operational Readiness",
            detail="QKG snapshot missing — knowledge documentation gap",
            evidence={"qkg_present": False},
            priority="P3",
            dependencies=["qkg"],
            next_action="Refresh Quant Knowledge Graph evidence",
        )

    eqs_alerts = _as_list(
        _as_dict(watches.get("incident_prioritization")).get("eqs_alerts")
    )
    if len(eqs_alerts) >= 2:
        add(
            "Validation required",
            category="Incident Prioritization",
            detail=f"{len(eqs_alerts)} EQS alerts require operator review",
            evidence={"alerts": eqs_alerts[:5]},
            priority="P1",
            dependencies=["eqs"],
            next_action="Investigate execution anomalies in EQS",
        )

    # Deduplicate by kind+detail prefix
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in recs:
        key = f"{r['kind']}|{str(r.get('detail'))[:80]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_work_queue(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_order = {p: i for i, p in enumerate(QUEUE_PRIORITIES)}
    queue = []
    for r in recommendations:
        queue.append(
            {
                "item_id": r.get("recommendation_id") or str(uuid4()),
                "priority": r.get("priority") or "P2",
                "evidence": r.get("evidence"),
                "owner": r.get("owner") or "ops-desk",
                "category": r.get("category") or "Operations",
                "dependencies": r.get("dependencies") or [],
                "suggested_next_action": r.get("suggested_next_action"),
                "kind": r.get("kind"),
                "detail": r.get("detail"),
                "requires_human_approval": True,
                "auto_remediation": False,
            }
        )
    queue.sort(key=lambda x: priority_order.get(str(x.get("priority")), 99))
    for i, item in enumerate(queue):
        item["queue_position"] = i + 1
    return queue


def build_executive_scores(
    ctx: dict[str, Any],
    health: dict[str, Any],
    watches: dict[str, Any],
) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    qcs_scores = _as_dict(_as_dict(sources.get("qcs")).get("scores") or sources.get("qcs"))
    qpm_health = _as_dict(
        _as_dict(watches.get("portfolio_watch")).get("health")
        or _as_dict(sources.get("qpm")).get("health")
    )
    icp_health = _as_dict(_as_dict(sources.get("icp")).get("health") or sources.get("icp"))
    iep_n = len(_as_list(_as_dict(watches.get("research_backlog")).get("experiments")))
    release = _score_or(
        45.0,
        qcs_scores.get("overall_institutional_readiness_score"),
        55.0 if _as_dict(watches.get("release_readiness")).get("certification_level") else 40.0,
    )
    platform = _score_or(
        50.0,
        icp_health.get("overall_platform_health"),
        health.get("overall_operational_health"),
    )
    research = _clamp(40.0 + min(40.0, iep_n * 5) + min(20.0, len(_as_list(_as_dict(watches.get("research_backlog")).get("aqs_recommendations"))) * 3))
    portfolio = _score_or(
        50.0,
        qpm_health.get("overall_portfolio_health"),
        _as_dict(_as_dict(watches.get("portfolio_watch")).get("metrics")).get(
            "portfolio_confidence_score"
        ),
    )
    operational = _score_or(
        50.0,
        health.get("overall_operational_health"),
        (
            _score_or(50.0, health.get("execution_score"))
            + _score_or(50.0, health.get("reliability_score"))
            + _score_or(50.0, health.get("validation_confidence"))
        )
        / 3.0,
    )
    scores = {
        "platform_readiness": platform,
        "research_readiness": research,
        "release_readiness": release,
        "portfolio_readiness": portfolio,
        "operational_readiness": operational,
    }
    return {k: scores[k] for k in EXECUTIVE_SCORE_KEYS}


def build_evidence_explorer(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    packs = []
    for sid in DATA_SOURCES:
        blob = sources.get(sid)
        packs.append(
            {
                "source": sid,
                "present": bool(blob),
                "summary_keys": list(_as_dict(blob).keys())[:12]
                if isinstance(blob, dict)
                else [],
                "evidence_ref": f"sources.{sid}",
            }
        )
    return {
        "packs": packs,
        "integrity": {
            "all_sources_listed": len(packs) == len(DATA_SOURCES),
            "unique_source_ids": len({p["source"] for p in packs}) == len(packs),
            "source_count": ctx.get("source_count"),
        },
    }


def build_reports(
    *,
    scores: dict[str, Any],
    recommendations: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    health: dict[str, Any],
    watches: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "daily_operations_brief": {
            "title": "Daily Operations Brief",
            "generated_at": now,
            "health": health,
            "queue_preview": queue[:10],
            "top_recommendations": recommendations[:8],
            "human_approval_required": True,
        },
        "weekly_executive_brief": {
            "title": "Weekly Executive Brief",
            "generated_at": now,
            "executive_scores": scores,
            "release_readiness": watches.get("release_readiness"),
            "portfolio_watch": watches.get("portfolio_watch"),
        },
        "platform_readiness_report": {
            "title": "Platform Readiness Report",
            "generated_at": now,
            "executive_scores": scores,
            "evidence_integrity": evidence.get("integrity"),
            "never_modifies_production": True,
        },
        "recommendation_report": {
            "title": "Recommendation Report",
            "generated_at": now,
            "recommendations": recommendations,
            "queue": queue,
            "auto_remediation": False,
            "requires_human_approval": True,
        },
    }


def recommendation_consistency_check(
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[str] = []
    for r in recommendations:
        if r.get("kind") not in RECOMMENDATION_KINDS:
            issues.append(f"invalid_kind:{r.get('kind')}")
        if not r.get("requires_human_approval"):
            issues.append("missing_human_approval_flag")
        if r.get("auto_applied") is True:
            issues.append("auto_applied_forbidden")
        if not r.get("evidence"):
            issues.append("missing_evidence")
        if not r.get("never_remediates_automatically"):
            issues.append("missing_no_remediation_flag")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_integrity_check(
    *,
    evidence: dict[str, Any],
    scores: dict[str, Any],
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[str] = []
    integrity = _as_dict(evidence.get("integrity"))
    if not integrity.get("all_sources_listed"):
        issues.append("evidence_incomplete")
    if not integrity.get("unique_source_ids"):
        issues.append("duplicate_source_ids")
    for key in EXECUTIVE_SCORE_KEYS:
        if key not in scores:
            issues.append(f"missing_score:{key}")
        else:
            v = _f(scores.get(key))
            if v is None or not (0.0 <= v <= 100.0):
                issues.append(f"score_out_of_range:{key}")
    for item in queue:
        if item.get("priority") not in QUEUE_PRIORITIES:
            issues.append("invalid_queue_priority")
        if item.get("auto_remediation") is True:
            issues.append("auto_remediation_forbidden")
        if not item.get("requires_human_approval"):
            issues.append("queue_missing_human_flag")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
