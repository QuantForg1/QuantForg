"""QSMR analytics — registry, discovery, comparison, scores, reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.quantforg_strategy_marketplace.models import (
    GROUP_FIELDS,
    SCORE_KEYS,
    SORT_FIELDS,
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


def build_scores_for_strategy(
    *,
    research: float,
    validation: float,
    risk: float,
    execution: float,
    certification: float,
) -> dict[str, Any]:
    overall = _clamp(
        research * 0.15
        + validation * 0.25
        + risk * 0.2
        + execution * 0.2
        + certification * 0.2
    )
    scores = {
        "overall_strategy_score": overall,
        "research_score": _clamp(research),
        "validation_score": _clamp(validation),
        "risk_score": _clamp(risk),
        "execution_score": _clamp(execution),
        "certification_score": _clamp(certification),
    }
    return {k: scores[k] for k in SCORE_KEYS}


def build_registry(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    islm = _as_dict(sources.get("islm"))
    strategies = _as_list(islm.get("registry"))
    irl = _as_dict(sources.get("irl"))
    experiments = _as_list(irl.get("experiments"))
    ise = _as_dict(sources.get("ise"))
    sims = _as_list(ise.get("simulations"))
    cvf = _as_dict(sources.get("cvf"))
    conf = _as_dict(cvf.get("confidence") or cvf)
    irap = _as_dict(sources.get("irap"))
    irap_metrics = _as_dict(irap.get("metrics") or irap)
    eqs = _as_dict(sources.get("eqs"))
    eqs_score = _as_dict(eqs.get("execution_score") or eqs)
    qcs = _as_dict(sources.get("qcs"))
    qcs_level = _as_dict(qcs.get("level") or qcs)
    qcs_scores = _as_dict(qcs.get("scores") or qcs)
    irdp = _as_dict(sources.get("irdp"))
    releases = _as_list(irdp.get("releases"))
    iep = _as_dict(sources.get("iep"))
    aqs = _as_dict(sources.get("aqs"))
    recs = _as_list(aqs.get("recommendations"))
    qkg = _as_dict(sources.get("qkg"))
    portfolio = _as_dict(sources.get("portfolio"))
    perf = _as_dict(_as_dict(portfolio.get("sections")).get("performance"))
    risk_sec = _as_dict(_as_dict(portfolio.get("sections")).get("risk"))

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

    replay_evidence = [
        {
            "simulation_id": _as_dict(s).get("simulation_id") or _as_dict(s).get("id"),
            "mode": _as_dict(s).get("mode") or _as_dict(s).get("scenario"),
            "metrics": _as_dict(s).get("metrics"),
        }
        for s in sims
        if isinstance(s, dict)
        and (
            "replay" in str(s.get("mode") or "").lower()
            or "historical" in str(s.get("mode") or s.get("scenario") or "").lower()
        )
    ]
    simulation_evidence = [
        {
            "simulation_id": _as_dict(s).get("simulation_id") or _as_dict(s).get("id"),
            "scenario": _as_dict(s).get("scenario") or _as_dict(s).get("mode"),
            "metrics": _as_dict(s).get("metrics"),
        }
        for s in sims[:20]
        if isinstance(s, dict)
    ]
    validation_evidence = {
        "confidence": conf.get("confidence"),
        "alerts": _as_list(cvf.get("alerts")),
        "observed_at": cvf.get("observed_at"),
    }
    risk_profile = {
        "metrics": irap_metrics,
        "portfolio_risk": risk_sec,
        "alerts": _as_list(irap.get("alerts")),
    }
    deployment_history = [
        {
            "release_id": _as_dict(r).get("release_id"),
            "version": _as_dict(r).get("version"),
            "status": _as_dict(r).get("status"),
            "stage": _as_dict(r).get("stage"),
        }
        for r in releases[:15]
    ]
    research_lineage = [
        {
            "experiment_id": _as_dict(e).get("experiment_id") or _as_dict(e).get("id"),
            "name": _as_dict(e).get("name") or _as_dict(e).get("title"),
            "status": _as_dict(e).get("status"),
        }
        for e in experiments[:20]
    ]
    research_lineage.extend(
        [
            {
                "recommendation_id": _as_dict(r).get("recommendation_id")
                or _as_dict(r).get("id"),
                "title": _as_dict(r).get("title") or _as_dict(r).get("summary"),
                "source": "aqs",
            }
            for r in recs[:10]
        ]
    )

    cert_status = str(
        qcs_level.get("level") or "Not Ready"
    )
    cert_score = _score_or(
        40.0,
        qcs_scores.get("overall_institutional_readiness_score"),
    )
    validation_score = _score_or(40.0, conf.get("confidence"))
    execution_score = _score_or(
        50.0, eqs_score.get("overall_execution_score")
    )
    dd = _f(risk_sec.get("max_drawdown_pct") or irap_metrics.get("maximum_drawdown"))
    risk_score = _clamp(100.0 - dd * 2.5) if dd is not None else 55.0
    research_score = _score_or(
        40.0 if research_lineage else 25.0,
        45.0 + min(30.0, len(research_lineage) * 3),
        _as_dict(_as_dict(irl.get("leaderboard")).get("top") or {}).get("composite"),
    )

    rows: list[dict[str, Any]] = []

    if strategies:
        for s in strategies:
            sd = _as_dict(s)
            sid = str(sd.get("strategy_id") or f"islm-{uuid4().hex[:8]}")
            health = _as_dict(sd.get("health"))
            lifecycle = str(sd.get("lifecycle_state") or "Draft")
            retired = lifecycle.lower() in {"retired", "suspended"}
            scores = build_scores_for_strategy(
                research=_score_or(research_score, health.get("research_score")),
                validation=_score_or(validation_score, health.get("validation_score")),
                risk=_score_or(risk_score, health.get("risk_score")),
                execution=_score_or(execution_score, health.get("execution_score")),
                certification=cert_score,
            )
            evidence = _as_dict(sd.get("evidence"))
            rows.append(
                {
                    "strategy_id": sid,
                    "strategy_name": str(sd.get("name") or sid),
                    "owner": str(sd.get("owner") or "quantforg-desk"),
                    "version": str(sd.get("version") or "1.0.0"),
                    "status": "Retired"
                    if retired
                    else ("Active" if "production" in lifecycle.lower() or "monitor" in lifecycle.lower() else "Research"),
                    "lifecycle": lifecycle,
                    "research_lineage": evidence.get("research_history") or research_lineage,
                    "replay_evidence": evidence.get("replay_results") or replay_evidence,
                    "simulation_evidence": evidence.get("simulation_results")
                    or simulation_evidence,
                    "validation_evidence": evidence.get("cvf_findings")
                    or validation_evidence,
                    "risk_profile": evidence.get("risk_analytics") or risk_profile,
                    "certification_status": cert_status,
                    "deployment_history": evidence.get("release_history")
                    or deployment_history,
                    "retirement_status": "Retired"
                    if lifecycle.lower() == "retired"
                    else ("Suspended" if lifecycle.lower() == "suspended" else "Active"),
                    "knowledge_graph_links": evidence.get("knowledge_graph_links")
                    or qkg_links[:20],
                    "scores": scores,
                    "performance": {
                        "expectancy": perf.get("expectancy"),
                        "profit_factor": perf.get("profit_factor"),
                        "sharpe_ratio": perf.get("sharpe_ratio"),
                    },
                    "origin": "islm",
                    "never_deploys": True,
                    "never_modifies_strategies": True,
                }
            )
    else:
        # Observational primary entry from portfolio / lab
        scores = build_scores_for_strategy(
            research=research_score,
            validation=validation_score,
            risk=risk_score,
            execution=execution_score,
            certification=cert_score,
        )
        rows.append(
            {
                "strategy_id": "xauusd-primary",
                "strategy_name": "XAUUSD Primary",
                "owner": "quantforg-desk",
                "version": str(
                    (deployment_history[0].get("version") if deployment_history else None)
                    or "1.0.0"
                ),
                "status": "Active" if portfolio else "Research",
                "lifecycle": "Monitoring" if portfolio else "Research",
                "research_lineage": research_lineage,
                "replay_evidence": replay_evidence,
                "simulation_evidence": simulation_evidence,
                "validation_evidence": validation_evidence,
                "risk_profile": risk_profile,
                "certification_status": cert_status,
                "deployment_history": deployment_history,
                "retirement_status": "Active",
                "knowledge_graph_links": qkg_links[:20],
                "scores": scores,
                "performance": {
                    "expectancy": perf.get("expectancy"),
                    "profit_factor": perf.get("profit_factor"),
                    "sharpe_ratio": perf.get("sharpe_ratio"),
                },
                "origin": "observational",
                "never_deploys": True,
                "never_modifies_strategies": True,
            }
        )

    # Lab experiments as research entries
    for e in experiments[:8]:
        ed = _as_dict(e)
        eid = str(ed.get("experiment_id") or ed.get("id") or uuid4().hex[:8])
        sid = f"lab-{eid}"
        if any(r.get("strategy_id") == sid for r in rows):
            continue
        scores = build_scores_for_strategy(
            research=_score_or(50.0, ed.get("composite"), ed.get("score")),
            validation=35.0,
            risk=45.0,
            execution=40.0,
            certification=30.0,
        )
        rows.append(
            {
                "strategy_id": sid,
                "strategy_name": str(ed.get("name") or ed.get("title") or eid),
                "owner": str(ed.get("owner") or "quantforg-research"),
                "version": str(ed.get("version") or "0.1.0"),
                "status": "Research",
                "lifecycle": "Research",
                "research_lineage": [ed],
                "replay_evidence": [],
                "simulation_evidence": [],
                "validation_evidence": {},
                "risk_profile": {},
                "certification_status": "Not Ready",
                "deployment_history": [],
                "retirement_status": "Active",
                "knowledge_graph_links": [],
                "scores": scores,
                "performance": {},
                "origin": "irl",
                "never_deploys": True,
                "never_modifies_strategies": True,
            }
        )

    # Attach IEP link count as metadata on primary
    if rows and _as_list(iep.get("registry")):
        rows[0]["experiment_links"] = [
            {
                "experiment_id": _as_dict(x).get("experiment_id"),
                "title": _as_dict(x).get("title"),
            }
            for x in _as_list(iep.get("registry"))[:5]
        ]

    return rows


def discover(
    registry: list[dict[str, Any]],
    *,
    q: str | None = None,
    status: str | None = None,
    lifecycle: str | None = None,
    owner: str | None = None,
    certification_status: str | None = None,
    sort_by: str = "overall_strategy_score",
    sort_dir: str = "desc",
    group_by: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    rows = list(registry)
    if q:
        needle = q.lower().strip()
        rows = [
            r
            for r in rows
            if needle
            in f"{r.get('strategy_id')} {r.get('strategy_name')} {r.get('owner')}".lower()
        ]
    if status:
        rows = [r for r in rows if str(r.get("status") or "").lower() == status.lower()]
    if lifecycle:
        rows = [
            r
            for r in rows
            if str(r.get("lifecycle") or "").lower() == lifecycle.lower()
        ]
    if owner:
        rows = [r for r in rows if str(r.get("owner") or "").lower() == owner.lower()]
    if certification_status:
        rows = [
            r
            for r in rows
            if str(r.get("certification_status") or "").lower()
            == certification_status.lower()
        ]

    field = sort_by if sort_by in SORT_FIELDS else "overall_strategy_score"
    reverse = sort_dir.lower() != "asc"

    def sort_key(r: dict[str, Any]) -> Any:
        if field in SCORE_KEYS:
            return _f(_as_dict(r.get("scores")).get(field)) or 0.0
        return str(r.get(field) or "")

    rows.sort(key=sort_key, reverse=reverse)
    rows = rows[:limit]

    groups: dict[str, list[dict[str, Any]]] | None = None
    if group_by and group_by in GROUP_FIELDS:
        groups = {}
        for r in rows:
            key = str(r.get(group_by) or "unknown")
            groups.setdefault(key, []).append(r)

    return {
        "results": rows,
        "count": len(rows),
        "filters": {
            "q": q,
            "status": status,
            "lifecycle": lifecycle,
            "owner": owner,
            "certification_status": certification_status,
        },
        "sort": {"by": field, "dir": "desc" if reverse else "asc"},
        "groups": groups,
        "group_by": group_by,
        "available_sort_fields": list(SORT_FIELDS),
        "available_group_fields": list(GROUP_FIELDS),
    }


def compare_strategies(
    registry: list[dict[str, Any]],
    strategy_ids: list[str] | None = None,
) -> dict[str, Any]:
    by_id = {str(r.get("strategy_id")): r for r in registry}
    ids = strategy_ids or [str(r.get("strategy_id")) for r in registry[:4]]
    selected = [by_id[i] for i in ids if i in by_id]
    if not selected:
        selected = registry[: min(4, len(registry))]

    dimensions = (
        "performance",
        "risk",
        "validation",
        "simulation",
        "certification",
        "health",
    )
    comparison = []
    for r in selected:
        scores = _as_dict(r.get("scores"))
        perf = _as_dict(r.get("performance"))
        risk = _as_dict(r.get("risk_profile"))
        comparison.append(
            {
                "strategy_id": r.get("strategy_id"),
                "strategy_name": r.get("strategy_name"),
                "performance": {
                    **perf,
                    "score": scores.get("overall_strategy_score"),
                },
                "risk": {
                    "score": scores.get("risk_score"),
                    "profile": risk,
                },
                "validation": {
                    "score": scores.get("validation_score"),
                    "evidence": r.get("validation_evidence"),
                },
                "simulation": {
                    "count": len(_as_list(r.get("simulation_evidence"))),
                    "evidence": _as_list(r.get("simulation_evidence"))[:5],
                },
                "certification": {
                    "status": r.get("certification_status"),
                    "score": scores.get("certification_score"),
                },
                "health": scores,
            }
        )

    # Rank by overall
    ranked = sorted(
        comparison,
        key=lambda c: _f(_as_dict(c.get("health")).get("overall_strategy_score"))
        or 0.0,
        reverse=True,
    )
    for i, row in enumerate(ranked):
        row["rank"] = i + 1

    return {
        "dimensions": list(dimensions),
        "strategies": ranked,
        "count": len(ranked),
        "read_only": True,
    }


def build_reports(registry: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    by_status: dict[str, int] = {}
    by_cert: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    for r in registry:
        by_status[str(r.get("status") or "unknown")] = (
            by_status.get(str(r.get("status") or "unknown"), 0) + 1
        )
        by_cert[str(r.get("certification_status") or "unknown")] = (
            by_cert.get(str(r.get("certification_status") or "unknown"), 0) + 1
        )
        by_lifecycle[str(r.get("lifecycle") or "unknown")] = (
            by_lifecycle.get(str(r.get("lifecycle") or "unknown"), 0) + 1
        )

    avg_overall = 0.0
    if registry:
        vals = [
            _f(_as_dict(r.get("scores")).get("overall_strategy_score")) or 0.0
            for r in registry
        ]
        avg_overall = round(sum(vals) / len(vals), 1)

    return {
        "strategy_registry": {
            "title": "Strategy Registry",
            "generated_at": now,
            "count": len(registry),
            "strategies": [
                {
                    "strategy_id": r.get("strategy_id"),
                    "strategy_name": r.get("strategy_name"),
                    "owner": r.get("owner"),
                    "version": r.get("version"),
                    "status": r.get("status"),
                    "lifecycle": r.get("lifecycle"),
                    "scores": r.get("scores"),
                }
                for r in registry[:50]
            ],
        },
        "portfolio_summary": {
            "title": "Portfolio Summary",
            "generated_at": now,
            "count": len(registry),
            "by_status": by_status,
            "by_lifecycle": by_lifecycle,
            "average_overall_score": avg_overall,
        },
        "certification_summary": {
            "title": "Certification Summary",
            "generated_at": now,
            "by_certification_status": by_cert,
            "entries": [
                {
                    "strategy_id": r.get("strategy_id"),
                    "certification_status": r.get("certification_status"),
                    "certification_score": _as_dict(r.get("scores")).get(
                        "certification_score"
                    ),
                }
                for r in registry[:50]
            ],
        },
        "version_report": {
            "title": "Version Report",
            "generated_at": now,
            "versions": [
                {
                    "strategy_id": r.get("strategy_id"),
                    "strategy_name": r.get("strategy_name"),
                    "version": r.get("version"),
                    "deployment_history": _as_list(r.get("deployment_history"))[:5],
                }
                for r in registry[:50]
            ],
        },
    }


def registry_consistency_check(registry: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(r.get("strategy_id") or "") for r in registry]
    if any(not i for i in ids):
        issues.append("missing_strategy_id")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_strategy_ids")
    for r in registry:
        scores = _as_dict(r.get("scores"))
        for key in SCORE_KEYS:
            if key not in scores:
                issues.append(f"missing_score:{key}")
            else:
                v = _f(scores.get(key))
                if v is None or not (0.0 <= v <= 100.0):
                    issues.append(f"score_out_of_range:{key}")
        if not r.get("never_deploys"):
            issues.append("deploy_flag_missing")
        if not r.get("never_modifies_strategies"):
            issues.append("modify_flag_missing")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_integrity_check(registry: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    for r in registry:
        for field in (
            "research_lineage",
            "replay_evidence",
            "simulation_evidence",
            "validation_evidence",
            "risk_profile",
            "deployment_history",
            "knowledge_graph_links",
        ):
            if field not in r:
                issues.append(f"missing_field:{field}:{r.get('strategy_id')}")
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "strategy_count": len(registry),
        "read_only": True,
    }
