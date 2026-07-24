"""QDIE analytics — scoring, recommendations, explainability, reports."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any

from app.domain.quantforg_decision_intelligence.models import (
    DECISION_CATEGORIES,
    DecisionCategory,
    PRIORITIES,
    SCORE_KEYS,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, round(value, 2)))


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return "qdie-" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_scores(ctx: dict[str, Any]) -> dict[str, float]:
    sources = _as_dict(ctx.get("sources"))
    avail = _as_dict(ctx.get("availability"))
    source_count = _num(ctx.get("source_count"), 0)

    cvf = _as_dict(sources.get("cvf"))
    conf = _as_dict(cvf.get("confidence") or cvf)
    validation = _num(conf.get("confidence"), 50.0)

    qcs = _as_dict(sources.get("qcs"))
    qcs_scores = _as_dict(qcs.get("scores") or qcs)
    cert = _num(
        qcs_scores.get("overall_institutional_readiness_score")
        or _as_dict(qcs.get("level") or {}).get("score"),
        50.0,
    )

    irap = _as_dict(sources.get("irap"))
    irap_m = _as_dict(irap.get("metrics") or irap)
    drawdown = _num(irap_m.get("maximum_drawdown"), 15.0)
    risk_score = _clamp(100.0 - drawdown * 2.0)

    qpm = _as_dict(sources.get("qpm"))
    qpm_m = _as_dict(qpm.get("metrics") or qpm)
    qpm_h = _as_dict(qpm.get("health") or {})
    portfolio = _num(
        qpm_m.get("portfolio_confidence_score")
        or qpm_h.get("overall_portfolio_health"),
        55.0,
    )

    eqs = _as_dict(sources.get("eqs"))
    eqs_s = _as_dict(eqs.get("execution_score") or eqs)
    execution = _num(eqs_s.get("overall_execution_score"), 60.0)

    res = _as_dict(sources.get("res"))
    res_s = _as_dict(res.get("reliability_score") or res)
    reliability = _num(res_s.get("overall_reliability_score"), 60.0)

    ise = _as_dict(sources.get("ise"))
    sims = _as_list(ise.get("simulations"))
    sim_consistency = _clamp(40.0 + min(len(sims), 20) * 2.5)

    iep = _as_dict(sources.get("iep"))
    exps = _as_list(iep.get("registry"))
    irl = _as_dict(sources.get("irl"))
    irl_exps = _as_list(irl.get("experiments"))
    research = _clamp(35.0 + min(len(exps) + len(irl_exps), 25) * 2.0)

    icp = _as_dict(sources.get("icp"))
    icp_h = _as_dict(icp.get("health") or icp)
    ops = _num(icp_h.get("overall_platform_health"), 55.0)

    aoc = _as_dict(sources.get("aoc"))
    aoc_scores = _as_dict(aoc.get("executive_scores") or aoc)
    if aoc_scores.get("operational_readiness") is not None:
        ops = _num(aoc_scores.get("operational_readiness"), ops)

    evidence_quality = _clamp(
        (source_count / max(len(avail) or 17, 1)) * 70.0
        + (10.0 if avail.get("qkg") else 0.0)
        + (10.0 if avail.get("qem") else 0.0)
        + (10.0 if avail.get("qcdm") else 0.0)
    )

    confidence = _clamp(
        (validation + cert + research + sim_consistency) / 4.0
    )
    overall = _clamp(
        confidence * 0.18
        + evidence_quality * 0.14
        + research * 0.12
        + validation * 0.14
        + sim_consistency * 0.10
        + portfolio * 0.12
        + ops * 0.12
        + ((execution + reliability) / 2.0) * 0.08
    )

    return {
        "confidence": confidence,
        "evidence_quality": evidence_quality,
        "research_quality": research,
        "validation_strength": validation,
        "simulation_consistency": sim_consistency,
        "portfolio_impact": portfolio,
        "operational_readiness": ops,
        "overall_decision_score": overall,
        "risk_health": risk_score,
        "execution_quality": execution,
        "reliability": reliability,
        "certification_readiness": cert,
    }


def _recommendation(
    *,
    category: str,
    priority: str,
    title: str,
    why: str,
    supporting: list[dict[str, Any]],
    conflicting: list[dict[str, Any]],
    dependencies: list[str],
    risk_assessment: str,
    next_actions: list[str],
    alternatives: list[str],
    trade_offs: list[str],
    limitations: list[str],
    scores: dict[str, float],
    confidence: float,
    evidence_score: float,
) -> dict[str, Any]:
    did = _stable_id(category, title, priority)
    return {
        "decision_id": did,
        "decision_category": category,
        "priority": priority,
        "title": title,
        "confidence_score": _clamp(confidence),
        "evidence_score": _clamp(evidence_score),
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "dependencies": dependencies,
        "risk_assessment": risk_assessment,
        "recommended_next_actions": next_actions,
        "human_approval_status": "pending",
        "requires_human_approval": True,
        "auto_applied": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "explainability": {
            "why": why,
            "evidence_used": [e.get("id") or e.get("source") for e in supporting],
            "alternative_options": alternatives,
            "trade_offs": trade_offs,
            "confidence_level": _clamp(confidence),
            "known_limitations": limitations,
        },
        "scores_snapshot": {k: scores.get(k) for k in SCORE_KEYS},
        "created_at": datetime.now(UTC).isoformat(),
        "read_only": True,
    }


def build_recommendations(
    ctx: dict[str, Any], scores: dict[str, float]
) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    recs: list[dict[str, Any]] = []

    validation = scores.get("validation_strength", 50.0)
    cert = scores.get("certification_readiness", 50.0)
    research = scores.get("research_quality", 50.0)
    portfolio = scores.get("portfolio_impact", 50.0)
    ops = scores.get("operational_readiness", 50.0)
    risk = scores.get("risk_health", 50.0)
    sim = scores.get("simulation_consistency", 50.0)
    overall = scores.get("overall_decision_score", 50.0)
    evidence_q = scores.get("evidence_quality", 50.0)

    # Research Decision
    iep_n = len(_as_list(_as_dict(sources.get("iep")).get("registry")))
    irl_n = len(_as_list(_as_dict(sources.get("irl")).get("experiments")))
    if research < 70 or iep_n + irl_n < 3:
        recs.append(
            _recommendation(
                category=DecisionCategory.RESEARCH.value,
                priority="P2" if research >= 55 else "P1",
                title="Expand research evidence before strategy promotion",
                why="Research and experiment coverage is below institutional threshold.",
                supporting=[
                    {"source": "iep", "id": "iep-registry", "note": f"{iep_n} experiments"},
                    {"source": "irl", "id": "irl-experiments", "note": f"{irl_n} lab experiments"},
                ],
                conflicting=[
                    {
                        "source": "qcs",
                        "id": "cert-pressure",
                        "note": "Certification may still proceed with caveats",
                    }
                ]
                if cert >= 60
                else [],
                dependencies=["iep", "irl", "ise"],
                risk_assessment="Low research depth increases false-promotion risk.",
                next_actions=[
                    "Open pending experiments in IEP",
                    "Complete at least one replay and one Monte Carlo simulation",
                    "Attach evidence IDs to strategy records",
                ],
                alternatives=[
                    "Defer strategy decisions until research score ≥ 70",
                    "Narrow scope to a single hypothesis experiment",
                ],
                trade_offs=[
                    "More research delays time-to-decision",
                    "Less research weakens explainability",
                ],
                limitations=["Research counts are observational snapshots only"],
                scores=scores,
                confidence=research,
                evidence_score=evidence_q,
            )
        )

    # Strategy Decision
    islm = _as_dict(sources.get("islm"))
    strategies = _as_list(islm.get("registry"))
    if strategies or scores.get("validation_strength", 0) < 65:
        recs.append(
            _recommendation(
                category=DecisionCategory.STRATEGY.value,
                priority="P1" if validation < 60 else "P2",
                title="Hold strategy lifecycle transitions pending validation",
                why="Strategy decisions should wait for stronger validation and human review.",
                supporting=[
                    {
                        "source": "islm",
                        "id": "islm-registry",
                        "note": f"{len(strategies)} strategies observed",
                    },
                    {
                        "source": "cvf",
                        "id": "cvf-confidence",
                        "note": f"validation={validation}",
                    },
                ],
                conflicting=[],
                dependencies=["islm", "cvf", "qcs"],
                risk_assessment="Premature lifecycle moves can pollute production readiness.",
                next_actions=[
                    "Review ISLM lifecycle states",
                    "Require human approval for any promote/retire action",
                    "Link QCS blockers to strategy IDs",
                ],
                alternatives=[
                    "Promote only paper-trade candidates",
                    "Archive stale research strategies",
                ],
                trade_offs=[
                    "Holding slows pipeline throughput",
                    "Promoting early increases operational risk",
                ],
                limitations=["QDIE never modifies strategy records"],
                scores=scores,
                confidence=_clamp((validation + research) / 2.0),
                evidence_score=evidence_q,
            )
        )

    # Validation Decision
    if validation < 75:
        recs.append(
            _recommendation(
                category=DecisionCategory.VALIDATION.value,
                priority="P0" if validation < 45 else "P1",
                title="Strengthen continuous validation before release review",
                why="Validation strength is below the advisory institutional bar.",
                supporting=[
                    {"source": "cvf", "id": "cvf-snapshot", "note": f"score={validation}"},
                    {"source": "qcs", "id": "qcs-scores", "note": f"cert={cert}"},
                ],
                conflicting=[
                    {"source": "ise", "id": "sim-ok", "note": f"sim_consistency={sim}"}
                ]
                if sim >= 70
                else [],
                dependencies=["cvf", "ise", "replay"],
                risk_assessment="Weak validation undermines release and portfolio decisions.",
                next_actions=[
                    "Re-run CVF confidence checks",
                    "Reconcile replay vs live drift",
                    "Document conflicting simulation evidence",
                ],
                alternatives=["Gate releases until validation ≥ 75", "Accept with explicit waiver"],
                trade_offs=["Stricter gates slow releases", "Waivers increase residual risk"],
                limitations=["Confidence metrics may lag recent experiments"],
                scores=scores,
                confidence=validation,
                evidence_score=evidence_q,
            )
        )

    # Risk Review
    irap_alerts = _as_list(_as_dict(sources.get("irap")).get("alerts"))
    if risk < 70 or irap_alerts:
        recs.append(
            _recommendation(
                category=DecisionCategory.RISK.value,
                priority="P0" if risk < 50 else "P1",
                title="Conduct formal risk review on elevated exposures",
                why="Risk health or alert inventory indicates need for human risk review.",
                supporting=[
                    {"source": "irap", "id": "irap-alerts", "note": f"{len(irap_alerts)} alerts"},
                    {"source": "irap", "id": "risk-health", "note": f"risk_health={risk}"},
                ],
                conflicting=[],
                dependencies=["irap", "qpm", "icp"],
                risk_assessment="Unresolved risk alerts can cascade into portfolio and ops decisions.",
                next_actions=[
                    "Triage IRAP alerts by severity",
                    "Map alerts to strategies and portfolios",
                    "Record human risk disposition",
                ],
                alternatives=["Tighten advisory risk limits", "Maintain status quo with monitoring"],
                trade_offs=["Tighter limits reduce opportunity", "Loose limits raise drawdown risk"],
                limitations=["QDIE never changes risk parameters"],
                scores=scores,
                confidence=risk,
                evidence_score=evidence_q,
            )
        )

    # Portfolio Review
    if portfolio < 70:
        recs.append(
            _recommendation(
                category=DecisionCategory.PORTFOLIO.value,
                priority="P1" if portfolio < 55 else "P2",
                title="Review portfolio allocation recommendations",
                why="Portfolio confidence/health is below advisory target.",
                supporting=[
                    {"source": "qpm", "id": "qpm-metrics", "note": f"portfolio={portfolio}"},
                ],
                conflicting=[],
                dependencies=["qpm", "irap", "islm"],
                risk_assessment="Allocation drift without review may concentrate risk.",
                next_actions=[
                    "Open QPM ranking and diversification views",
                    "Compare concentration vs risk alerts",
                    "Require human approval before any capital change",
                ],
                alternatives=["Rebalance advisory weights", "Defer allocation changes"],
                trade_offs=["Rebalancing incurs turnover", "Deferral preserves current exposures"],
                limitations=["QDIE never allocates capital"],
                scores=scores,
                confidence=portfolio,
                evidence_score=evidence_q,
            )
        )

    # Release Review
    releases = _as_list(_as_dict(sources.get("irdp")).get("releases"))
    if cert < 80 or releases:
        recs.append(
            _recommendation(
                category=DecisionCategory.RELEASE.value,
                priority="P0" if cert < 50 else "P1",
                title="Defer release approval until certification clears",
                why="Release decisions require certification readiness and explicit human approval.",
                supporting=[
                    {"source": "qcs", "id": "qcs-level", "note": f"cert={cert}"},
                    {"source": "irdp", "id": "releases", "note": f"{len(releases)} releases"},
                    {"source": "cvf", "id": "validation", "note": f"validation={validation}"},
                ],
                conflicting=[],
                dependencies=["qcs", "irdp", "cvf", "aoc"],
                risk_assessment="Approving releases without certification risks production integrity.",
                next_actions=[
                    "Review QCS blockers",
                    "Confirm IRDP approval queue remains human-gated",
                    "Publish decision brief for release committee",
                ],
                alternatives=["Approve with documented waiver", "Rollback candidate release"],
                trade_offs=["Deferral slows delivery", "Waiver increases operational risk"],
                limitations=["QDIE never approves releases"],
                scores=scores,
                confidence=_clamp((cert + validation) / 2.0),
                evidence_score=evidence_q,
            )
        )

    # Operational Review
    aoc_recs = _as_list(_as_dict(sources.get("aoc")).get("recommendations"))
    if ops < 70 or aoc_recs:
        recs.append(
            _recommendation(
                category=DecisionCategory.OPERATIONAL.value,
                priority="P1" if ops < 55 else "P2",
                title="Operational readiness review with AOC evidence",
                why="Platform operational score or AOC queue indicates operator attention needed.",
                supporting=[
                    {"source": "icp", "id": "icp-health", "note": f"ops={ops}"},
                    {"source": "aoc", "id": "aoc-recs", "note": f"{len(aoc_recs)} AOC items"},
                    {"source": "eqs", "id": "execution", "note": f"eq={scores.get('execution_quality')}"},
                    {"source": "res", "id": "reliability", "note": f"rel={scores.get('reliability')}"},
                ],
                conflicting=[],
                dependencies=["aoc", "icp", "eqs", "res", "qem"],
                risk_assessment="Operational gaps can block safe research-to-release flow.",
                next_actions=[
                    "Walk AOC work queue with operators",
                    "Correlate QEM alerts to incidents",
                    "Confirm no automatic remediation is enabled",
                ],
                alternatives=["Increase monitoring only", "Escalate P0 ops items"],
                trade_offs=["Escalation consumes operator time", "Ignoring raises incident probability"],
                limitations=["QDIE never performs automatic actions"],
                scores=scores,
                confidence=ops,
                evidence_score=evidence_q,
            )
        )

    # Always ensure at least an executive overview recommendation when overall is middling
    if not recs:
        recs.append(
            _recommendation(
                category=DecisionCategory.OPERATIONAL.value,
                priority="P3",
                title="Maintain advisory monitoring posture",
                why=f"Overall decision score {overall} is within acceptable advisory band.",
                supporting=[
                    {"source": "qdie", "id": "scores", "note": f"overall={overall}"},
                    {"source": "qcdm", "id": "contract", "note": "canonical contract available"},
                ],
                conflicting=[],
                dependencies=["qem", "qcdm", "qkg"],
                risk_assessment="Residual risk is low; continue human oversight.",
                next_actions=["Continue scheduled decision reviews", "Keep human approval gates intact"],
                alternatives=["Increase review cadence", "Reduce review cadence"],
                trade_offs=["More reviews cost time", "Fewer reviews reduce early detection"],
                limitations=["Snapshot-based; not a live guarantee"],
                scores=scores,
                confidence=overall,
                evidence_score=evidence_q,
            )
        )

    priority_rank = {p: i for i, p in enumerate(PRIORITIES)}
    recs.sort(
        key=lambda r: (
            priority_rank.get(str(r.get("priority")), 99),
            -_num(r.get("confidence_score"), 0),
        )
    )
    return recs


def build_evidence_graph(
    ctx: dict[str, Any], recommendations: list[dict[str, Any]]
) -> dict[str, Any]:
    avail = _as_dict(ctx.get("availability"))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for src, ok in avail.items():
        nodes.append(
            {
                "id": str(src),
                "type": "source",
                "available": bool(ok),
            }
        )
    for rec in recommendations:
        rid = str(rec.get("decision_id"))
        nodes.append(
            {
                "id": rid,
                "type": "decision",
                "category": rec.get("decision_category"),
                "priority": rec.get("priority"),
            }
        )
        for ev in _as_list(rec.get("supporting_evidence")):
            src = str(_as_dict(ev).get("source") or "unknown")
            edges.append(
                {
                    "from": src,
                    "to": rid,
                    "relation": "supports",
                    "evidence_id": _as_dict(ev).get("id"),
                }
            )
        for ev in _as_list(rec.get("conflicting_evidence")):
            src = str(_as_dict(ev).get("source") or "unknown")
            edges.append(
                {
                    "from": src,
                    "to": rid,
                    "relation": "conflicts",
                    "evidence_id": _as_dict(ev).get("id"),
                }
            )
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "read_only": True,
    }


def build_tradeoff_viewer(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in recommendations:
        exp = _as_dict(rec.get("explainability"))
        rows.append(
            {
                "decision_id": rec.get("decision_id"),
                "title": rec.get("title"),
                "category": rec.get("decision_category"),
                "alternatives": exp.get("alternative_options") or [],
                "trade_offs": exp.get("trade_offs") or [],
                "limitations": exp.get("known_limitations") or [],
                "confidence_level": exp.get("confidence_level"),
            }
        )
    return rows


def build_reports(
    *,
    scores: dict[str, float],
    recommendations: list[dict[str, Any]],
    evidence_graph: dict[str, Any],
) -> dict[str, Any]:
    top = recommendations[:5]
    return {
        "decision_report": {
            "title": "QDIE Decision Report",
            "overall_decision_score": scores.get("overall_decision_score"),
            "scores": {k: scores.get(k) for k in SCORE_KEYS},
            "recommendation_count": len(recommendations),
            "top_recommendations": [
                {
                    "decision_id": r.get("decision_id"),
                    "title": r.get("title"),
                    "priority": r.get("priority"),
                    "category": r.get("decision_category"),
                }
                for r in top
            ],
            "human_approval_required": True,
            "read_only": True,
        },
        "executive_decision_brief": {
            "headline": "Advisory decision posture",
            "overall_decision_score": scores.get("overall_decision_score"),
            "p0_count": sum(1 for r in recommendations if r.get("priority") == "P0"),
            "p1_count": sum(1 for r in recommendations if r.get("priority") == "P1"),
            "key_messages": [r.get("title") for r in top[:3]],
            "never_auto_acts": True,
            "read_only": True,
        },
        "recommendation_summary": {
            "by_category": {
                cat: sum(1 for r in recommendations if r.get("decision_category") == cat)
                for cat in DECISION_CATEGORIES
            },
            "items": [
                {
                    "decision_id": r.get("decision_id"),
                    "priority": r.get("priority"),
                    "title": r.get("title"),
                    "human_approval_status": r.get("human_approval_status"),
                }
                for r in recommendations
            ],
            "read_only": True,
        },
        "decision_history": {
            "note": "Chronological advisory decisions from this run (immutable snapshot)",
            "entries": [
                {
                    "decision_id": r.get("decision_id"),
                    "created_at": r.get("created_at"),
                    "category": r.get("decision_category"),
                    "priority": r.get("priority"),
                    "title": r.get("title"),
                    "human_approval_status": r.get("human_approval_status"),
                }
                for r in recommendations
            ],
            "evidence_edge_count": evidence_graph.get("edge_count"),
            "read_only": True,
        },
    }


def decision_consistency_check(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(r.get("decision_id") or "") for r in recommendations]
    if any(not i for i in ids):
        issues.append("missing_decision_id")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_decision_ids")
    for r in recommendations:
        if r.get("decision_category") not in DECISION_CATEGORIES:
            issues.append(f"invalid_category:{r.get('decision_category')}")
        if r.get("priority") not in PRIORITIES:
            issues.append(f"invalid_priority:{r.get('priority')}")
        if r.get("requires_human_approval") is not True:
            issues.append("missing_human_approval_flag")
        if r.get("auto_applied") is not False:
            issues.append("auto_applied_must_be_false")
        if r.get("human_approval_status") != "pending":
            issues.append("approval_must_start_pending")
        if r.get("never_executes_trades") is not True:
            issues.append("must_never_execute_trades")
        if r.get("never_modifies_production") is not True:
            issues.append("must_never_modify_production")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_consistency_check(
    recommendations: list[dict[str, Any]], evidence_graph: dict[str, Any]
) -> dict[str, Any]:
    issues: list[str] = []
    edge_targets = {
        str(e.get("to"))
        for e in _as_list(evidence_graph.get("edges"))
        if isinstance(e, dict)
    }
    for r in recommendations:
        rid = str(r.get("decision_id"))
        supporting = _as_list(r.get("supporting_evidence"))
        if not supporting:
            issues.append(f"no_supporting_evidence:{rid}")
        if rid not in edge_targets and supporting:
            issues.append(f"missing_graph_edges:{rid}")
        for ev in supporting:
            if not _as_dict(ev).get("source"):
                issues.append(f"evidence_missing_source:{rid}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def explainability_validation(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    required = (
        "why",
        "evidence_used",
        "alternative_options",
        "trade_offs",
        "confidence_level",
        "known_limitations",
    )
    for r in recommendations:
        exp = _as_dict(r.get("explainability"))
        rid = r.get("decision_id")
        for key in required:
            if key not in exp:
                issues.append(f"missing_explain:{rid}:{key}")
        if not exp.get("why"):
            issues.append(f"empty_why:{rid}")
        if not _as_list(exp.get("alternative_options")):
            issues.append(f"no_alternatives:{rid}")
        if not _as_list(exp.get("trade_offs")):
            issues.append(f"no_tradeoffs:{rid}")
        if not _as_list(exp.get("known_limitations")):
            issues.append(f"no_limitations:{rid}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
