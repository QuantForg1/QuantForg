"""ISLM analytics — registry, health, alerts, evidence, reports (advisory)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_strategy_lifecycle.models import (
    LIFECYCLE_ORDER,
    LifecycleState,
)

DEFAULT_STRATEGY_ID = "xauusd-primary"
DEFAULT_OWNER = "quantforg-desk"


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
            return _clamp(v)
    return _clamp(default)


def infer_lifecycle_state(evidence: dict[str, Any]) -> str:
    """Derive observational stage from evidence completeness — never auto-promotes."""
    if evidence.get("suspended"):
        return LifecycleState.SUSPENDED.value
    if evidence.get("retired"):
        return LifecycleState.RETIRED.value
    has_research = bool(evidence.get("research_history"))
    has_replay = bool(evidence.get("replay_results"))
    has_sim = bool(evidence.get("simulation_results"))
    has_cvf = bool(evidence.get("cvf_findings"))
    has_risk = bool(evidence.get("risk_analytics"))
    has_release = bool(evidence.get("release_history"))
    in_prod = bool(evidence.get("production_signals"))
    monitoring = bool(evidence.get("monitoring_signals"))

    if monitoring and in_prod:
        return LifecycleState.MONITORING.value
    if in_prod:
        return LifecycleState.PRODUCTION.value
    if has_release:
        return LifecycleState.RELEASE_APPROVAL.value
    if has_risk:
        return LifecycleState.RISK_REVIEW.value
    if has_cvf:
        return LifecycleState.CONTINUOUS_VALIDATION.value
    if has_sim:
        return LifecycleState.SIMULATION_VALIDATION.value
    if has_replay:
        return LifecycleState.REPLAY_VALIDATION.value
    if has_research:
        return LifecycleState.RESEARCH.value
    return LifecycleState.DRAFT.value


def next_lifecycle_state(current: str) -> str | None:
    try:
        idx = LIFECYCLE_ORDER.index(current)
    except ValueError:
        return LifecycleState.DRAFT.value
    # Suspended/Retired are terminal-ish; Monitoring can go to Suspended
    if current == LifecycleState.RETIRED.value:
        return None
    if current == LifecycleState.SUSPENDED.value:
        return LifecycleState.RETIRED.value
    if current == LifecycleState.MONITORING.value:
        return LifecycleState.SUSPENDED.value
    if idx + 1 < len(LIFECYCLE_ORDER):
        nxt = LIFECYCLE_ORDER[idx + 1]
        if nxt in (
            LifecycleState.SUSPENDED.value,
            LifecycleState.RETIRED.value,
        ) and current != LifecycleState.MONITORING.value:
            return None
        return nxt
    return None


def build_health_scores(
    *,
    research: float,
    validation: float,
    execution: float,
    reliability: float,
    risk: float,
) -> dict[str, Any]:
    overall = _clamp(
        research * 0.15
        + validation * 0.25
        + execution * 0.2
        + reliability * 0.2
        + risk * 0.2
    )
    return {
        "research_score": _clamp(research),
        "validation_score": _clamp(validation),
        "execution_score": _clamp(execution),
        "reliability_score": _clamp(reliability),
        "risk_score": _clamp(risk),
        "overall_strategy_health": overall,
        "weights": {
            "research": 0.15,
            "validation": 0.25,
            "execution": 0.2,
            "reliability": 0.2,
            "risk": 0.2,
        },
    }


def build_registry_from_sources(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    portfolio = _as_dict(sources.get("portfolio"))
    sections = _as_dict(portfolio.get("sections"))
    perf = _as_dict(sections.get("performance"))
    risk_sec = _as_dict(sections.get("risk"))
    sic = _as_dict(sources.get("sic"))
    irl = _as_dict(sources.get("irl"))
    aqs = _as_dict(sources.get("aqs"))
    ise = _as_dict(sources.get("ise"))
    cvf = _as_dict(sources.get("cvf"))
    irap = _as_dict(sources.get("irap"))
    eqs = _as_dict(sources.get("eqs"))
    res = _as_dict(sources.get("res"))
    irdp = _as_list(sources.get("irdp"))
    qkg = _as_dict(sources.get("qkg"))

    experiments = _as_list(irl.get("experiments"))
    sims = _as_list(ise.get("simulations"))
    recs = _as_list(aqs.get("recommendations"))
    conf = _as_dict(cvf.get("confidence") or cvf)
    eqs_score = _as_dict(eqs.get("execution_score") or eqs)
    res_score = _as_dict(res.get("reliability_score") or res)
    irap_metrics = _as_dict(irap.get("metrics") or irap)

    qkg_links: list[dict[str, Any]] = []
    for node in _as_list(qkg.get("nodes")):
        nd = _as_dict(node)
        label = str(nd.get("label") or nd.get("id") or "")
        ntype = str(nd.get("type") or nd.get("kind") or "").lower()
        if "strateg" in ntype or "strateg" in label.lower():
            qkg_links.append(
                {
                    "node_id": nd.get("id") or nd.get("node_id"),
                    "label": label,
                    "type": ntype,
                }
            )

    research_history = [
        {
            "experiment_id": _as_dict(e).get("experiment_id")
            or _as_dict(e).get("id"),
            "name": _as_dict(e).get("name") or _as_dict(e).get("title"),
            "status": _as_dict(e).get("status"),
        }
        for e in experiments[:20]
    ]
    if recs:
        research_history.extend(
            [
                {
                    "recommendation_id": _as_dict(r).get("recommendation_id")
                    or _as_dict(r).get("id"),
                    "title": _as_dict(r).get("title") or _as_dict(r).get("summary"),
                    "source": "aqs",
                }
                for r in recs[:15]
            ]
        )

    replay_results = []
    for s in sims:
        sd = _as_dict(s)
        mode = str(sd.get("mode") or sd.get("scenario") or "").lower()
        if "replay" in mode or "historical" in mode:
            replay_results.append(
                {
                    "simulation_id": sd.get("simulation_id") or sd.get("id"),
                    "mode": sd.get("mode") or sd.get("scenario"),
                    "metrics": sd.get("metrics"),
                }
            )

    simulation_results = [
        {
            "simulation_id": _as_dict(s).get("simulation_id") or _as_dict(s).get("id"),
            "scenario": _as_dict(s).get("scenario") or _as_dict(s).get("mode"),
            "metrics": _as_dict(s).get("metrics"),
        }
        for s in sims[:20]
    ]

    cvf_findings = {
        "confidence": conf.get("confidence"),
        "alerts": _as_list(cvf.get("alerts")),
        "observed_at": cvf.get("observed_at"),
    }
    risk_analytics = {
        "metrics": irap_metrics,
        "alerts": _as_list(irap.get("alerts")),
        "observed_at": irap.get("observed_at"),
    }
    execution_quality = {
        "overall_execution_score": eqs_score.get("overall_execution_score"),
        "alerts": _as_list(eqs.get("alerts")),
        "observed_at": eqs.get("observed_at"),
    }
    reliability = {
        "overall_reliability_score": res_score.get("overall_reliability_score"),
        "alerts": _as_list(res.get("alerts")),
        "observed_at": res.get("observed_at"),
    }
    release_history = [
        {
            "release_id": _as_dict(r).get("release_id"),
            "version": _as_dict(r).get("version"),
            "status": _as_dict(r).get("status"),
            "stage": _as_dict(r).get("stage"),
        }
        for r in irdp[:20]
    ]

    research_score = _score_or(
        40.0 if research_history else 20.0,
        _as_dict(_as_dict(irl.get("leaderboard")).get("top") or {}).get("composite"),
        len(research_history) * 4,
    )
    validation_score = _score_or(
        35.0,
        conf.get("confidence"),
        50.0 + min(30.0, len(simulation_results) * 5),
    )
    execution_score = _score_or(
        50.0, eqs_score.get("overall_execution_score")
    )
    reliability_score = _score_or(
        50.0, res_score.get("overall_reliability_score")
    )
    # Higher risk score = healthier (invert drawdown / VaR pressure)
    dd = _f(risk_sec.get("max_drawdown_pct") or irap_metrics.get("maximum_drawdown"))
    sharpe = _f(perf.get("sharpe_ratio") or irap_metrics.get("sharpe_ratio"))
    risk_score = 55.0
    if dd is not None:
        risk_score = _clamp(100.0 - dd * 2.5)
    if sharpe is not None:
        risk_score = _clamp((risk_score + min(100.0, max(0.0, sharpe * 40))) / 2)

    health = build_health_scores(
        research=research_score,
        validation=validation_score,
        execution=execution_score,
        reliability=reliability_score,
        risk=risk_score,
    )

    evidence = {
        "research_history": research_history,
        "replay_results": replay_results,
        "simulation_results": simulation_results,
        "cvf_findings": cvf_findings if cvf else {},
        "risk_analytics": risk_analytics if irap or risk_sec else {},
        "execution_quality": execution_quality if eqs else {},
        "reliability": reliability if res else {},
        "release_history": release_history,
        "knowledge_graph_links": qkg_links[:30],
        "production_signals": bool(portfolio.get("trade_count") or perf),
        "monitoring_signals": bool(
            _as_list(eqs.get("alerts"))
            or _as_list(res.get("alerts"))
            or _as_list(irap.get("alerts"))
            or _as_list(cvf.get("alerts"))
        ),
        "sic_summary": {
            "keys": list(sic.keys())[:12] if sic else [],
            "present": bool(sic),
        },
    }

    inferred = infer_lifecycle_state(evidence)
    version = "1.0.0"
    if release_history:
        version = str(
            release_history[0].get("version")
            or f"1.0.{len(release_history)}"
        )

    primary = {
        "strategy_id": DEFAULT_STRATEGY_ID,
        "name": "XAUUSD Primary",
        "owner": DEFAULT_OWNER,
        "version": version,
        "lifecycle_state": inferred,
        "recommended_lifecycle_state": inferred,
        "recommended_next_state": next_lifecycle_state(inferred),
        "requires_human_approval_to_advance": True,
        "never_auto_promotes": True,
        "never_auto_retires": True,
        "health": health,
        "evidence": evidence,
        "version_history": [
            {
                "version": version,
                "at": datetime.now(UTC).isoformat(),
                "note": "Observational sync from evidence sources",
                "lifecycle_state": inferred,
            }
        ],
    }

    rows = [primary]

    # Lab experiments as draft/research registry entries
    for e in experiments[:12]:
        ed = _as_dict(e)
        sid = str(
            ed.get("experiment_id")
            or ed.get("id")
            or f"exp-{uuid4().hex[:8]}"
        )
        rows.append(
            {
                "strategy_id": f"lab-{sid}",
                "name": str(ed.get("name") or ed.get("title") or sid),
                "owner": str(ed.get("owner") or DEFAULT_OWNER),
                "version": str(ed.get("version") or "0.1.0"),
                "lifecycle_state": LifecycleState.RESEARCH.value
                if ed
                else LifecycleState.DRAFT.value,
                "recommended_lifecycle_state": LifecycleState.RESEARCH.value,
                "recommended_next_state": LifecycleState.REPLAY_VALIDATION.value,
                "requires_human_approval_to_advance": True,
                "never_auto_promotes": True,
                "never_auto_retires": True,
                "health": build_health_scores(
                    research=_score_or(45.0, ed.get("score"), ed.get("composite")),
                    validation=30.0,
                    execution=40.0,
                    reliability=40.0,
                    risk=45.0,
                ),
                "evidence": {
                    "research_history": [ed],
                    "replay_results": [],
                    "simulation_results": [],
                    "cvf_findings": {},
                    "risk_analytics": {},
                    "execution_quality": {},
                    "reliability": {},
                    "release_history": [],
                    "knowledge_graph_links": [],
                },
                "version_history": [],
                "origin": "irl",
            }
        )

    return rows


def build_alerts(strategies: list[dict[str, Any]], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    sources = _as_dict(ctx.get("sources"))
    portfolio = _as_dict(sources.get("portfolio"))
    risk_sec = _as_dict(_as_dict(portfolio.get("sections")).get("risk"))
    eqs = _as_dict(sources.get("eqs"))
    res = _as_dict(sources.get("res"))
    cvf = _as_dict(sources.get("cvf"))
    irap = _as_dict(sources.get("irap"))

    dd = _f(risk_sec.get("max_drawdown_pct") or risk_sec.get("current_drawdown_pct"))
    if dd is not None and dd >= 20:
        alerts.append(
            {
                "kind": "High drawdown",
                "severity": "critical" if dd >= 30 else "warning",
                "detail": f"Observed drawdown {dd}%",
                "read_only": True,
            }
        )

    conf = _f(_as_dict(cvf.get("confidence") or cvf).get("confidence"))
    if conf is not None and conf < 45:
        alerts.append(
            {
                "kind": "Validation drift",
                "severity": "warning",
                "detail": f"CVF confidence {conf}",
                "read_only": True,
            }
        )

    eq = _f(
        _as_dict(eqs.get("execution_score") or eqs).get("overall_execution_score")
    )
    if eq is not None and eq < 60:
        alerts.append(
            {
                "kind": "Execution degradation",
                "severity": "warning",
                "detail": f"EQS overall {eq}",
                "read_only": True,
            }
        )

    res_alerts = _as_list(res.get("alerts"))
    incident_n = len(res_alerts)
    if incident_n >= 3:
        alerts.append(
            {
                "kind": "Repeated incidents",
                "severity": "warning",
                "detail": f"{incident_n} reliability alerts in snapshot",
                "read_only": True,
            }
        )

    for s in strategies:
        health = _as_dict(s.get("health"))
        overall = _f(health.get("overall_strategy_health"))
        if overall is not None and overall < 55:
            alerts.append(
                {
                    "kind": "Performance degradation",
                    "severity": "warning",
                    "detail": (
                        f"{s.get('strategy_id')} overall health {overall}"
                    ),
                    "strategy_id": s.get("strategy_id"),
                    "read_only": True,
                }
            )

    # Surface nested IRAP/CVF alert kinds without mutating them
    for raw in _as_list(irap.get("alerts"))[:5]:
        ad = _as_dict(raw)
        alerts.append(
            {
                "kind": str(ad.get("kind") or "Risk signal"),
                "severity": str(ad.get("severity") or "info"),
                "detail": str(ad.get("detail") or ad.get("message") or ""),
                "source": "irap",
                "read_only": True,
            }
        )

    return alerts


def build_timeline(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = _as_dict(strategy.get("evidence"))
    events: list[dict[str, Any]] = []
    state = str(strategy.get("lifecycle_state") or LifecycleState.DRAFT.value)
    try:
        current_idx = LIFECYCLE_ORDER.index(state)
    except ValueError:
        current_idx = 0

    for i, stage in enumerate(LIFECYCLE_ORDER):
        status = "pending"
        if i < current_idx:
            status = "completed"
        elif i == current_idx:
            status = "current"
        events.append(
            {
                "stage": stage,
                "status": status,
                "requires_human_approval": True,
                "auto_transition": False,
            }
        )

    # Evidence anchors
    for key, label in (
        ("research_history", "Research evidence"),
        ("replay_results", "Replay evidence"),
        ("simulation_results", "Simulation evidence"),
        ("cvf_findings", "CVF evidence"),
        ("risk_analytics", "Risk evidence"),
        ("release_history", "Release evidence"),
    ):
        blob = evidence.get(key)
        present = bool(blob) if not isinstance(blob, dict) else any(blob.values())
        if present:
            events.append(
                {
                    "stage": label,
                    "status": "evidence",
                    "count": len(blob) if isinstance(blob, list) else 1,
                }
            )
    return events


def build_reports(
    *,
    strategies: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = strategies[0] if strategies else {}
    health = _as_dict(primary.get("health"))
    evidence = _as_dict(primary.get("evidence"))
    return {
        "strategy_timeline": {
            "title": "Strategy Timeline",
            "strategies": [
                {
                    "strategy_id": s.get("strategy_id"),
                    "lifecycle_state": s.get("lifecycle_state"),
                    "timeline": build_timeline(s),
                }
                for s in strategies[:10]
            ],
        },
        "version_history": {
            "title": "Version History",
            "entries": [
                {
                    "strategy_id": s.get("strategy_id"),
                    "version": s.get("version"),
                    "history": _as_list(s.get("version_history")),
                }
                for s in strategies[:10]
            ],
        },
        "lifecycle_report": {
            "title": "Lifecycle Report",
            "states": LIFECYCLE_ORDER,
            "counts": {
                st: sum(1 for s in strategies if s.get("lifecycle_state") == st)
                for st in LIFECYCLE_ORDER
            },
            "human_approval_required": True,
            "never_auto_promotes": True,
            "never_auto_retires": True,
        },
        "health_report": {
            "title": "Health Report",
            "primary": health,
            "registry": [
                {
                    "strategy_id": s.get("strategy_id"),
                    "health": s.get("health"),
                }
                for s in strategies
            ],
        },
        "evidence_report": {
            "title": "Evidence Report",
            "primary_strategy_id": primary.get("strategy_id"),
            "evidence": evidence,
            "alert_count": len(alerts),
            "integrity": {
                "has_unique_ids": all(bool(s.get("strategy_id")) for s in strategies),
                "lifecycle_in_enum": all(
                    s.get("lifecycle_state") in LIFECYCLE_ORDER for s in strategies
                ),
            },
        },
    }


def merge_with_store(
    derived: list[dict[str, Any]],
    stored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(s.get("strategy_id")): dict(s) for s in stored if s.get("strategy_id")}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in derived:
        sid = str(row.get("strategy_id"))
        prev = by_id.get(sid) or {}
        merged = {**row, **{k: v for k, v in prev.items() if k in (
            "lifecycle_locked",
            "last_approver",
            "last_approved_at",
            "owner",
        ) and v is not None}}
        if prev.get("lifecycle_locked") and prev.get("lifecycle_state"):
            merged["lifecycle_state"] = prev["lifecycle_state"]
            merged["lifecycle_locked"] = True
            hist = list(prev.get("version_history") or [])
            if hist:
                merged["version_history"] = hist
        out.append(merged)
        seen.add(sid)
    for sid, prev in by_id.items():
        if sid not in seen:
            out.append(prev)
    return out
