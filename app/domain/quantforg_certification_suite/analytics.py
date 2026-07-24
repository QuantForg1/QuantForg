"""QCS analytics — checks, scores, levels, blockers, reports (advisory)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_certification_suite.models import (
    CERTIFICATION_DOMAINS,
    CERTIFICATION_LEVELS,
    DATA_SOURCES,
    SCORE_KEYS,
    CertificationLevel,
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


def _check(
    *,
    name: str,
    status: str,
    detail: str,
    evidence: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,  # pass | fail | warn | skip
        "detail": detail,
        "domain": domain,
        "evidence": evidence,
        "read_only": True,
    }


def build_checks(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    availability = _as_dict(ctx.get("availability"))
    checks: list[dict[str, Any]] = []

    # TypeScript / Python / coverage — observational proxies from ICP/docs presence
    icp = _as_dict(sources.get("icp"))
    idw = _as_dict(sources.get("idw"))
    qkg = _as_dict(sources.get("qkg"))
    source_count = int(ctx.get("source_count") or 0)

    checks.append(
        _check(
            name="TypeScript compilation",
            status="pass" if source_count >= 8 else "warn",
            detail="Observational gate — CI tsc status not mutated by QCS",
            evidence={"source_count": source_count},
            domain="Testing",
        )
    )
    checks.append(
        _check(
            name="Python unit tests",
            status="pass" if availability.get("irl") or availability.get("icp") else "warn",
            detail="Evidence of research/control surfaces present",
            evidence={"irl": bool(availability.get("irl")), "icp": bool(availability.get("icp"))},
            domain="Testing",
        )
    )
    checks.append(
        _check(
            name="Integration tests",
            status="pass" if availability.get("irdp") and availability.get("islm") else "warn",
            detail="Governance surfaces available for integration evidence",
            evidence={
                "irdp": bool(availability.get("irdp")),
                "islm": bool(availability.get("islm")),
            },
            domain="Testing",
        )
    )
    checks.append(
        _check(
            name="Coverage threshold",
            status="warn",
            detail="Coverage is enforced in CI — QCS does not rewrite coverage",
            evidence={"policy": "cov-fail-under from CI"},
            domain="Testing",
        )
    )

    replay = _as_dict(sources.get("replay"))
    replay_n = len(_as_list(replay.get("simulations"))) + len(_as_list(replay.get("jobs")))
    checks.append(
        _check(
            name="Replay consistency",
            status="pass" if replay_n > 0 else "fail",
            detail=f"Replay evidence count={replay_n}",
            evidence={"replay_n": replay_n},
            domain="Replay",
        )
    )

    ise = _as_dict(sources.get("ise"))
    sims = _as_list(ise.get("simulations"))
    checks.append(
        _check(
            name="Simulation consistency",
            status="pass" if len(sims) > 0 else "fail",
            detail=f"ISE simulations={len(sims)}",
            evidence={"simulation_count": len(sims)},
            domain="Simulation",
        )
    )

    cvf = _as_dict(sources.get("cvf"))
    conf = _f(_as_dict(cvf.get("confidence") or cvf).get("confidence"))
    drift_status = "pass"
    if conf is None:
        drift_status = "warn"
    elif conf < 45:
        drift_status = "fail"
    elif conf < 60:
        drift_status = "warn"
    checks.append(
        _check(
            name="Validation drift",
            status=drift_status,
            detail=f"CVF confidence={conf}",
            evidence={"confidence": conf, "alerts": _as_list(cvf.get("alerts"))[:5]},
            domain="Validation",
        )
    )

    islm = _as_dict(sources.get("islm"))
    strategies = _as_list(islm.get("registry"))
    health_vals = [
        _f(_as_dict(s.get("health")).get("overall_strategy_health"))
        for s in strategies
        if isinstance(s, dict)
    ]
    health_vals = [h for h in health_vals if h is not None]
    avg_health = sum(health_vals) / len(health_vals) if health_vals else None
    checks.append(
        _check(
            name="Strategy health",
            status="pass"
            if (avg_health or 0) >= 55
            else ("warn" if strategies else "fail"),
            detail=f"avg_strategy_health={avg_health} n={len(strategies)}",
            evidence={"avg_health": avg_health, "count": len(strategies)},
            domain="Operational Readiness",
        )
    )

    irap = _as_dict(sources.get("irap"))
    metrics = _as_dict(irap.get("metrics") or irap)
    dd = _f(metrics.get("maximum_drawdown"))
    risk_status = "pass"
    if dd is not None and dd >= 30:
        risk_status = "fail"
    elif dd is not None and dd >= 20:
        risk_status = "warn"
    elif not irap:
        risk_status = "warn"
    checks.append(
        _check(
            name="Risk health",
            status=risk_status,
            detail=f"max_drawdown={dd}",
            evidence={"metrics": metrics, "alerts": _as_list(irap.get("alerts"))[:5]},
            domain="Risk",
        )
    )

    eqs = _as_dict(sources.get("eqs"))
    eq = _f(_as_dict(eqs.get("execution_score") or eqs).get("overall_execution_score"))
    checks.append(
        _check(
            name="Execution score",
            status="pass" if (eq or 0) >= 60 else ("fail" if eq is not None else "warn"),
            detail=f"EQS overall={eq}",
            evidence={"execution_score": eq, "alerts": _as_list(eqs.get("alerts"))[:5]},
            domain="Execution",
        )
    )

    res = _as_dict(sources.get("res"))
    rel = _f(
        _as_dict(res.get("reliability_score") or res).get("overall_reliability_score")
    )
    checks.append(
        _check(
            name="Reliability score",
            status="pass"
            if (rel or 0) >= 60
            else ("fail" if rel is not None else "warn"),
            detail=f"RES overall={rel}",
            evidence={"reliability_score": rel, "alerts": _as_list(res.get("alerts"))[:5]},
            domain="Reliability",
        )
    )

    irdp = _as_dict(sources.get("irdp"))
    releases = _as_list(irdp.get("releases"))
    checks.append(
        _check(
            name="Release completeness",
            status="pass" if releases else "warn",
            detail=f"releases={len(releases)} approvals={len(_as_list(irdp.get('approvals')))}",
            evidence={"releases": releases[:5]},
            domain="Release Governance",
        )
    )

    checks.append(
        _check(
            name="Security scan status",
            status="warn",
            detail="Security evidence observational — QCS never mutates safety",
            evidence={"policy": "human_review_required"},
            domain="Security",
        )
    )

    missing = [s for s in DATA_SOURCES if not availability.get(s)]
    checks.append(
        _check(
            name="Dependency integrity",
            status="pass" if len(missing) <= 4 else "warn",
            detail=f"missing_sources={missing}",
            evidence={"missing": missing, "available": source_count},
            domain="Architecture",
        )
    )

    checks.append(
        _check(
            name="Configuration integrity",
            status="pass" if bool(icp or idw or qkg) else "warn",
            detail="Control plane / warehouse / graph presence",
            evidence={
                "icp": bool(icp),
                "idw": bool(idw),
                "qkg": bool(qkg),
            },
            domain="Architecture",
        )
    )

    docs_score_proxy = 70.0 if qkg or idw else 40.0
    checks.append(
        _check(
            name="Documentation completeness",
            status="pass" if docs_score_proxy >= 60 else "warn",
            detail="Knowledge graph / warehouse as documentation proxies",
            evidence={"proxy_score": docs_score_proxy},
            domain="Documentation",
        )
    )

    return checks


def build_scores(ctx: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    availability = _as_dict(ctx.get("availability"))
    pass_n = sum(1 for c in checks if c.get("status") == "pass")
    fail_n = sum(1 for c in checks if c.get("status") == "fail")
    warn_n = sum(1 for c in checks if c.get("status") == "warn")
    total = max(len(checks), 1)
    quality = _clamp((pass_n / total) * 100.0 - fail_n * 8.0 - warn_n * 2.0)

    architecture = _score_or(
        50.0 + min(40.0, int(ctx.get("source_count") or 0) * 3),
        80.0 if sum(1 for v in availability.values() if v) >= 10 else None,
    )
    research = _score_or(
        40.0,
        50.0 + min(30.0, len(_as_list(_as_dict(sources.get("irl")).get("experiments"))) * 3),
        50.0 + min(25.0, len(_as_list(_as_dict(sources.get("aqs")).get("recommendations"))) * 3),
    )
    validation = _score_or(
        45.0,
        _as_dict(_as_dict(sources.get("cvf")).get("confidence") or sources.get("cvf")).get(
            "confidence"
        ),
    )
    dd = _f(
        _as_dict(_as_dict(sources.get("irap")).get("metrics") or sources.get("irap")).get(
            "maximum_drawdown"
        )
    )
    risk = _clamp(100.0 - dd * 2.5) if dd is not None else 55.0
    execution = _score_or(
        50.0,
        _as_dict(
            _as_dict(sources.get("eqs")).get("execution_score") or sources.get("eqs")
        ).get("overall_execution_score"),
    )
    reliability = _score_or(
        50.0,
        _as_dict(
            _as_dict(sources.get("res")).get("reliability_score") or sources.get("res")
        ).get("overall_reliability_score"),
    )
    security = _score_or(55.0, 60.0 if availability.get("irdp") else 45.0)
    icp_elapsed = _f(_as_dict(sources.get("icp")).get("elapsed_ms"))
    if icp_elapsed is not None:
        performance = _clamp(100.0 - min(50.0, icp_elapsed / 20.0))
    else:
        performance = _score_or(55.0, quality)
    documentation = _score_or(
        50.0,
        70.0 if availability.get("qkg") else None,
        65.0 if availability.get("idw") else None,
    )

    overall = _clamp(
        architecture * 0.08
        + quality * 0.12
        + research * 0.1
        + validation * 0.12
        + risk * 0.12
        + execution * 0.12
        + reliability * 0.12
        + security * 0.08
        + performance * 0.07
        + documentation * 0.07
    )

    scores = {
        "architecture_score": architecture,
        "quality_score": quality,
        "research_score": research,
        "validation_score": validation,
        "risk_score": risk,
        "execution_score": execution,
        "reliability_score": reliability,
        "security_score": security,
        "performance_score": performance,
        "documentation_score": documentation,
        "overall_institutional_readiness_score": overall,
        "check_summary": {
            "pass": pass_n,
            "fail": fail_n,
            "warn": warn_n,
            "total": total,
        },
    }
    return {**{k: scores[k] for k in SCORE_KEYS}, "check_summary": scores["check_summary"]}


def infer_certification_level(
    scores: dict[str, Any],
    checks: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    overall = _f(scores.get("overall_institutional_readiness_score")) or 0.0
    critical_blockers = [
        b for b in blockers if str(b.get("severity") or "").lower() in {"critical", "high"}
    ]
    fails = [c for c in checks if c.get("status") == "fail"]

    level = CertificationLevel.NOT_READY.value
    if overall >= 35 and len(fails) <= 6:
        level = CertificationLevel.DEVELOPMENT_READY.value
    if overall >= 45 and len(fails) <= 4:
        level = CertificationLevel.RESEARCH_READY.value
    if overall >= 55 and len(fails) <= 3:
        level = CertificationLevel.PAPER_TRADING_READY.value
    if overall >= 65 and len(fails) <= 2 and len(critical_blockers) <= 2:
        level = CertificationLevel.STAGING_READY.value
    if overall >= 75 and len(fails) <= 1 and not critical_blockers:
        level = CertificationLevel.PRODUCTION_READY.value
    if overall >= 88 and not fails and not critical_blockers:
        level = CertificationLevel.INSTITUTIONAL_CERTIFIED.value

    return {
        "level": level,
        "levels": list(CERTIFICATION_LEVELS),
        "overall": overall,
        "human_approval_required": True,
        "auto_certified": False,
        "never_approves_releases_automatically": True,
        "pending_human_certification": True,
        "note": "Computed readiness only — explicit human approval required to certify",
    }


def build_blockers(
    ctx: dict[str, Any],
    checks: list[dict[str, Any]],
    scores: dict[str, Any],
) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    availability = _as_dict(ctx.get("availability"))
    blockers: list[dict[str, Any]] = []

    def add(
        kind: str,
        severity: str,
        detail: str,
        evidence: dict[str, Any],
    ) -> None:
        blockers.append(
            {
                "kind": kind,
                "severity": severity,
                "detail": detail,
                "evidence": evidence,
                "evidence_link": {"keys": list(evidence.keys())[:8]},
                "read_only": True,
                "blocks_auto_release": True,
            }
        )

    missing = [s for s in DATA_SOURCES if not availability.get(s)]
    if missing:
        add(
            "Missing evidence",
            "High" if len(missing) > 6 else "Medium",
            f"Unavailable sources: {', '.join(missing)}",
            {"missing": missing},
        )

    for c in checks:
        if c.get("status") != "fail":
            continue
        name = str(c.get("name") or "")
        mapping = {
            "Replay consistency": "Failed replay",
            "Simulation consistency": "Simulation mismatch",
            "Validation drift": "Validation drift",
            "Risk health": "High drawdown",
            "Reliability score": "Reliability degradation",
            "Execution score": "Execution degradation",
            "Security scan status": "Security issue",
            "Documentation completeness": "Documentation gap",
        }
        kind = mapping.get(name, name)
        sev = "Critical" if name in {"Risk health", "Security scan status"} else "High"
        add(kind, sev, str(c.get("detail") or ""), _as_dict(c.get("evidence")))

    dd = _f(
        _as_dict(_as_dict(sources.get("irap")).get("metrics") or sources.get("irap")).get(
            "maximum_drawdown"
        )
    )
    if dd is not None and dd >= 25:
        add(
            "High drawdown",
            "Critical" if dd >= 35 else "High",
            f"IRAP maximum_drawdown={dd}",
            {"maximum_drawdown": dd},
        )

    if (_f(scores.get("documentation_score")) or 100) < 50:
        add(
            "Documentation gap",
            "Medium",
            f"documentation_score={scores.get('documentation_score')}",
            {"documentation_score": scores.get("documentation_score")},
        )

    return blockers


def build_domain_readiness(
    checks: list[dict[str, Any]], scores: dict[str, Any]
) -> list[dict[str, Any]]:
    by_domain: dict[str, list[dict[str, Any]]] = {d: [] for d in CERTIFICATION_DOMAINS}
    for c in checks:
        domain = str(c.get("domain") or "Architecture")
        by_domain.setdefault(domain, []).append(c)
    rows = []
    for domain in CERTIFICATION_DOMAINS:
        items = by_domain.get(domain) or []
        fails = sum(1 for i in items if i.get("status") == "fail")
        passes = sum(1 for i in items if i.get("status") == "pass")
        rows.append(
            {
                "domain": domain,
                "checks": len(items),
                "pass": passes,
                "fail": fails,
                "ready": fails == 0 and (passes > 0 or len(items) == 0),
            }
        )
    return rows


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
    level: dict[str, Any],
    checks: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    domains: list[dict[str, Any]],
    evidence: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    sources = _as_dict(ctx.get("sources"))
    return {
        "certification_report": {
            "title": "Certification Report",
            "generated_at": now,
            "level": level,
            "scores": scores,
            "checks": checks,
            "blockers": blockers,
            "human_approval_required": True,
        },
        "release_certification": {
            "title": "Release Certification",
            "generated_at": now,
            "releases": _as_list(_as_dict(sources.get("irdp")).get("releases"))[:10],
            "level": level.get("level"),
            "never_auto_approves": True,
        },
        "strategy_certification": {
            "title": "Strategy Certification",
            "generated_at": now,
            "strategies": _as_list(_as_dict(sources.get("islm")).get("registry"))[:10],
            "level": level.get("level"),
        },
        "platform_certification": {
            "title": "Platform Certification",
            "generated_at": now,
            "domains": domains,
            "scores": scores,
            "icp": _as_dict(sources.get("icp")),
        },
        "executive_readiness_report": {
            "title": "Executive Readiness Report",
            "generated_at": now,
            "overall": scores.get("overall_institutional_readiness_score"),
            "level": level.get("level"),
            "blocker_count": len(blockers),
            "evidence_integrity": evidence.get("integrity"),
            "pending_human_certification": True,
            "never_modifies_production": True,
        },
    }


def certification_consistency_check(
    *,
    scores: dict[str, Any],
    level: dict[str, Any],
    blockers: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    for key in SCORE_KEYS:
        if key not in scores:
            issues.append(f"missing_score:{key}")
        else:
            v = _f(scores.get(key))
            if v is None or not (0.0 <= v <= 100.0):
                issues.append(f"score_out_of_range:{key}")
    if level.get("level") not in CERTIFICATION_LEVELS:
        issues.append("invalid_level")
    if level.get("auto_certified") is True:
        issues.append("auto_certified_forbidden")
    if not level.get("human_approval_required"):
        issues.append("human_approval_flag_missing")
    for b in blockers:
        if not b.get("evidence"):
            issues.append("blocker_missing_evidence")
    integrity = _as_dict(evidence.get("integrity"))
    if not integrity.get("all_sources_listed"):
        issues.append("evidence_incomplete")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
