"""ICP analytics — health scores, alerts, timeline, dependencies, reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_control_plane.models import (
    ALERT_SEVERITIES,
    DEPENDENCY_EDGES,
    HEALTH_SCORE_KEYS,
    SUBSYSTEMS,
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
            # Normalize 0-1 ratios to 0-100
            if 0.0 <= v <= 1.0 and v != 0:
                return _clamp(v * 100.0)
            return _clamp(v)
    return _clamp(default)


def _normalize_severity(raw: Any) -> str:
    text = str(raw or "medium").strip().lower()
    if text in {"critical", "crit", "p0"}:
        return "Critical"
    if text in {"high", "error", "danger", "p1"}:
        return "High"
    if text in {"medium", "warn", "warning", "p2"}:
        return "Medium"
    return "Informational"


def build_health_scores(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    icc = _as_dict(sources.get("icc"))
    icc_kpis = _as_dict(icc.get("executive_kpis") or _as_dict(icc.get("sections")).get("executive_kpis"))
    eqs = _as_dict(sources.get("eqs"))
    eqs_score = _as_dict(eqs.get("execution_score") or eqs)
    res = _as_dict(sources.get("res"))
    res_score = _as_dict(res.get("reliability_score") or res)
    cvf = _as_dict(sources.get("cvf"))
    conf = _as_dict(cvf.get("confidence") or cvf)
    ise = _as_dict(sources.get("ise"))
    sims = _as_list(ise.get("simulations"))
    iep = _as_dict(sources.get("iep"))
    iep_reg = _as_list(iep.get("registry"))
    irap = _as_dict(sources.get("irap"))
    irap_metrics = _as_dict(irap.get("metrics") or irap)
    irdp = _as_dict(sources.get("irdp"))
    releases = _as_list(irdp.get("releases"))
    aqs = _as_dict(sources.get("aqs"))
    recs = _as_list(aqs.get("recommendations"))
    idw = _as_dict(sources.get("idw"))
    quality = _as_dict(idw.get("quality") or idw.get("analytics"))
    islm = _as_dict(sources.get("islm"))
    strategies = _as_list(islm.get("registry"))

    trading = _score_or(
        55.0,
        icc_kpis.get("trading_health"),
        icc_kpis.get("live_trading_score"),
        _as_dict(icc.get("system_overall")).get("score"),
        icc.get("system_overall") if isinstance(icc.get("system_overall"), (int, float)) else None,
    )
    execution = _score_or(
        50.0, eqs_score.get("overall_execution_score"), eqs.get("overall_execution_score")
    )
    reliability = _score_or(
        50.0,
        res_score.get("overall_reliability_score"),
        _as_dict(res.get("platform_health")).get("overall_health"),
    )
    validation = _score_or(50.0, conf.get("confidence"))
    research = _score_or(
        45.0 if recs or strategies else 35.0,
        50.0 + min(30.0, len(recs) * 3),
        quality.get("overall_score"),
        quality.get("quality_score"),
    )
    simulation = _score_or(
        40.0 if not sims else min(90.0, 50.0 + len(sims) * 5),
        55.0 if sims else 40.0,
    )
    # Experiment health from primary IEP stats generalization / count
    exp_gen = None
    if iep_reg:
        exp_gen = _f(
            _as_dict(iep_reg[0].get("statistics")).get("generalization_score")
        )
    experiment = _score_or(
        45.0 if iep_reg else 35.0,
        exp_gen,
        50.0 + min(25.0, len(iep_reg) * 4),
    )
    # Risk: invert drawdown pressure
    dd = _f(irap_metrics.get("maximum_drawdown"))
    risk = 55.0
    if dd is not None:
        risk = _clamp(100.0 - dd * 2.5)
    risk = _score_or(
        risk,
        irap_metrics.get("sharpe_ratio") and min(100.0, (_f(irap_metrics.get("sharpe_ratio")) or 0) * 40),
    )
    # Release health
    release = 50.0
    if releases:
        statuses = [str(_as_dict(r).get("status") or "").lower() for r in releases]
        approved = sum(1 for s in statuses if "approv" in s or "prod" in s or "staged" in s)
        release = _clamp(45.0 + approved * 10.0 + min(20.0, len(releases) * 3))

    overall = _clamp(
        trading * 0.12
        + execution * 0.12
        + reliability * 0.12
        + validation * 0.12
        + research * 0.08
        + simulation * 0.08
        + experiment * 0.08
        + risk * 0.14
        + release * 0.14
    )

    scores = {
        "overall_platform_health": overall,
        "trading_health": trading,
        "execution_health": execution,
        "reliability_health": reliability,
        "validation_health": validation,
        "research_health": research,
        "simulation_health": simulation,
        "experiment_health": experiment,
        "risk_health": risk,
        "release_health": release,
    }
    return {
        **{k: scores[k] for k in HEALTH_SCORE_KEYS},
        "weights": {
            "trading": 0.12,
            "execution": 0.12,
            "reliability": 0.12,
            "validation": 0.12,
            "research": 0.08,
            "simulation": 0.08,
            "experiment": 0.08,
            "risk": 0.14,
            "release": 0.14,
        },
        "subsystem_availability": _as_dict(ctx.get("availability")),
    }


def _alert(
    *,
    severity: str,
    kind: str,
    detail: str,
    source: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "severity": _normalize_severity(severity),
        "kind": kind,
        "detail": detail,
        "source_subsystem": source,
        "evidence": evidence,
        "evidence_link": {
            "subsystem": source,
            "keys": list(evidence.keys())[:8],
        },
        "read_only": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def build_executive_alerts(ctx: dict[str, Any], health: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    alerts: list[dict[str, Any]] = []

    overall = _f(health.get("overall_platform_health")) or 100.0
    if overall < 40:
        alerts.append(
            _alert(
                severity="Critical",
                kind="Platform health critical",
                detail=f"Overall platform health {overall}",
                source="icp",
                evidence={"overall_platform_health": overall},
            )
        )
    elif overall < 55:
        alerts.append(
            _alert(
                severity="High",
                kind="Platform health degraded",
                detail=f"Overall platform health {overall}",
                source="icp",
                evidence={"overall_platform_health": overall},
            )
        )

    for key, sev_floor, severity in (
        ("execution_health", 50, "High"),
        ("reliability_health", 50, "High"),
        ("validation_health", 45, "Medium"),
        ("risk_health", 45, "High"),
        ("release_health", 40, "Medium"),
    ):
        val = _f(health.get(key))
        if val is not None and val < sev_floor:
            alerts.append(
                _alert(
                    severity=severity,
                    kind=f"{key.replace('_', ' ').title()} low",
                    detail=f"{key}={val}",
                    source="icp",
                    evidence={key: val},
                )
            )

    # Propagate nested alerts with evidence links
    for src_key in ("eqs", "res", "cvf", "irap"):
        nested = _as_list(_as_dict(sources.get(src_key)).get("alerts"))
        for raw in nested[:8]:
            ad = _as_dict(raw)
            if not ad:
                continue
            alerts.append(
                _alert(
                    severity=ad.get("severity") or "Medium",
                    kind=str(ad.get("kind") or ad.get("title") or f"{src_key} alert"),
                    detail=str(ad.get("detail") or ad.get("message") or ""),
                    source=src_key,
                    evidence=ad,
                )
            )

    icc_alerts_blob = _as_dict(sources.get("icc"))
    icc_sections = _as_dict(icc_alerts_blob.get("sections"))
    icc_alerts_raw = icc_sections.get("alerts") or icc_alerts_blob.get("alerts")
    if isinstance(icc_alerts_raw, dict):
        icc_nested = _as_list(
            icc_alerts_raw.get("items") or icc_alerts_raw.get("alerts")
        )
    else:
        icc_nested = _as_list(icc_alerts_raw)
    for raw in icc_nested[:8]:
        ad = _as_dict(raw)
        if not ad:
            continue
        alerts.append(
            _alert(
                severity=ad.get("severity") or "Medium",
                kind=str(ad.get("kind") or ad.get("title") or "icc alert"),
                detail=str(ad.get("detail") or ad.get("message") or ""),
                source="icc",
                evidence=ad,
            )
        )

    # Availability gaps
    availability = _as_dict(ctx.get("availability"))
    missing = [s for s in SUBSYSTEMS if not availability.get(s)]
    if missing:
        alerts.append(
            _alert(
                severity="Informational",
                kind="Subsystem evidence gaps",
                detail=f"No snapshot for: {', '.join(missing)}",
                source="icp",
                evidence={"missing": missing},
            )
        )

    # Sort Critical → Informational
    order = {s: i for i, s in enumerate(ALERT_SEVERITIES)}
    alerts.sort(key=lambda a: order.get(str(a.get("severity")), 99))
    return alerts


def build_global_timeline(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    events: list[dict[str, Any]] = []

    for rel in _as_list(_as_dict(sources.get("irdp")).get("releases"))[:10]:
        rd = _as_dict(rel)
        events.append(
            {
                "kind": "release",
                "title": f"Release {rd.get('version') or rd.get('release_id')}",
                "status": rd.get("status"),
                "at": rd.get("updated_at") or rd.get("created_at"),
                "evidence": {"release_id": rd.get("release_id"), "stage": rd.get("stage")},
                "source_subsystem": "irdp",
            }
        )

    for exp in _as_list(_as_dict(sources.get("iep")).get("registry"))[:10]:
        ed = _as_dict(exp)
        events.append(
            {
                "kind": "experiment",
                "title": str(ed.get("title") or ed.get("experiment_id")),
                "status": ed.get("lifecycle_state"),
                "at": ed.get("updated_at") or ed.get("created_at"),
                "evidence": {
                    "experiment_id": ed.get("experiment_id"),
                    "hypothesis": ed.get("hypothesis"),
                },
                "source_subsystem": "iep",
            }
        )

    for strat in _as_list(_as_dict(sources.get("islm")).get("registry"))[:8]:
        sd = _as_dict(strat)
        events.append(
            {
                "kind": "strategy_lifecycle",
                "title": str(sd.get("name") or sd.get("strategy_id")),
                "status": sd.get("lifecycle_state"),
                "at": sd.get("updated_at") or sd.get("created_at"),
                "evidence": {
                    "strategy_id": sd.get("strategy_id"),
                    "version": sd.get("version"),
                },
                "source_subsystem": "islm",
            }
        )

    for appr in _as_list(_as_dict(sources.get("islm")).get("approvals"))[:5]:
        ad = _as_dict(appr)
        events.append(
            {
                "kind": "strategy_lifecycle",
                "title": f"Lifecycle approval {ad.get('decision')}",
                "status": ad.get("to_state"),
                "at": ad.get("created_at"),
                "evidence": ad,
                "source_subsystem": "islm",
            }
        )

    for src, label in (("cvf", "validation"), ("irap", "risk"), ("res", "reliability"), ("eqs", "execution")):
        for raw in _as_list(_as_dict(sources.get(src)).get("alerts"))[:5]:
            ad = _as_dict(raw)
            events.append(
                {
                    "kind": f"{label}_alert" if label != "execution" else "execution_anomaly",
                    "title": str(ad.get("kind") or f"{src} alert"),
                    "status": ad.get("severity"),
                    "at": ad.get("observed_at") or ad.get("created_at"),
                    "evidence": ad,
                    "source_subsystem": src,
                }
            )

    # ICC timeline if present
    icc_tl = _as_list(
        _as_dict(_as_dict(sources.get("icc")).get("sections")).get("operational_timeline")
        or _as_dict(sources.get("icc")).get("operational_timeline")
    )
    if isinstance(
        _as_dict(_as_dict(sources.get("icc")).get("sections")).get("operational_timeline"),
        dict,
    ):
        icc_tl = _as_list(
            _as_dict(
                _as_dict(_as_dict(sources.get("icc")).get("sections")).get(
                    "operational_timeline"
                )
            ).get("events")
            or icc_tl
        )
    for raw in icc_tl[:10]:
        ad = _as_dict(raw)
        events.append(
            {
                "kind": str(ad.get("kind") or "icc_event"),
                "title": str(ad.get("title") or ad.get("summary") or "ICC event"),
                "status": ad.get("status"),
                "at": ad.get("at") or ad.get("observed_at") or ad.get("ts"),
                "evidence": ad,
                "source_subsystem": "icc",
            }
        )

    events.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    return events[:80]


def build_dependency_map(ctx: dict[str, Any]) -> dict[str, Any]:
    availability = _as_dict(ctx.get("availability"))
    nodes = [
        {
            "id": sid,
            "label": sid.upper(),
            "available": bool(availability.get(sid)),
            "role": "subsystem",
        }
        for sid in SUBSYSTEMS
    ]
    edges = [
        {
            "from": a,
            "to": b,
            "relation": "depends_on",
            "active": bool(availability.get(a)) and bool(availability.get(b)),
        }
        for a, b in DEPENDENCY_EDGES
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "read_only": True,
    }


def build_evidence_center(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    packs = []
    for sid in SUBSYSTEMS:
        blob = sources.get(sid)
        present = bool(blob)
        summary_keys: list[str] = []
        if isinstance(blob, dict):
            summary_keys = list(blob.keys())[:12]
        packs.append(
            {
                "subsystem": sid,
                "present": present,
                "summary_keys": summary_keys,
                "evidence_ref": f"sources.{sid}",
            }
        )
    return {
        "packs": packs,
        "source_count": ctx.get("source_count"),
        "integrity": {
            "all_subsystems_listed": len(packs) == len(SUBSYSTEMS),
            "unique_subsystem_ids": len({p["subsystem"] for p in packs}) == len(packs),
        },
    }


def build_reports(
    *,
    health: dict[str, Any],
    alerts: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    dependencies: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    critical_n = sum(1 for a in alerts if a.get("severity") == "Critical")
    high_n = sum(1 for a in alerts if a.get("severity") == "High")
    brief = {
        "title": "Executive Daily Brief",
        "period": "daily",
        "generated_at": now,
        "overall_platform_health": health.get("overall_platform_health"),
        "alert_counts": {
            "Critical": critical_n,
            "High": high_n,
            "Medium": sum(1 for a in alerts if a.get("severity") == "Medium"),
            "Informational": sum(
                1 for a in alerts if a.get("severity") == "Informational"
            ),
        },
        "top_alerts": alerts[:8],
        "timeline_preview": timeline[:10],
    }
    weekly = {
        "title": "Weekly Operations Review",
        "period": "weekly",
        "generated_at": now,
        "health": health,
        "dependency_summary": {
            "nodes": dependencies.get("node_count"),
            "edges": dependencies.get("edge_count"),
        },
        "timeline_count": len(timeline),
    }
    monthly = {
        "title": "Monthly Platform Review",
        "period": "monthly",
        "generated_at": now,
        "health": health,
        "evidence_integrity": evidence.get("integrity"),
        "alerts": alerts[:20],
    }
    quarterly = {
        "title": "Quarterly Executive Report",
        "period": "quarterly",
        "generated_at": now,
        "health": health,
        "dependencies": dependencies,
        "evidence": evidence,
        "alert_counts": brief["alert_counts"],
        "never_modifies_production": True,
    }
    return {
        "executive_daily_brief": brief,
        "weekly_operations_review": weekly,
        "monthly_platform_review": monthly,
        "quarterly_executive_report": quarterly,
    }


def aggregation_consistency_check(
    *,
    health: dict[str, Any],
    alerts: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    for key in HEALTH_SCORE_KEYS:
        if key not in health:
            issues.append(f"missing_health:{key}")
        else:
            v = _f(health.get(key))
            if v is None or not (0.0 <= v <= 100.0):
                issues.append(f"health_out_of_range:{key}")
    for a in alerts:
        if a.get("severity") not in ALERT_SEVERITIES:
            issues.append("alert_severity_invalid")
        if not a.get("evidence_link"):
            issues.append("alert_missing_evidence_link")
    integrity = _as_dict(evidence.get("integrity"))
    if not integrity.get("all_subsystems_listed"):
        issues.append("evidence_subsystems_incomplete")
    if not integrity.get("unique_subsystem_ids"):
        issues.append("evidence_duplicate_ids")
    return {"ok": len(issues) == 0, "issues": issues, "research_only": False, "read_only": True}
