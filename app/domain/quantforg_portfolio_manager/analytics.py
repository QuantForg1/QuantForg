"""QPM analytics — allocation, ranking, diversification, recommendations."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_portfolio_manager.models import (
    METRIC_KEYS,
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
    return round(max(lo, min(hi, n)), 2)


def _score_or(default: float, *candidates: Any) -> float:
    for c in candidates:
        v = _f(c)
        if v is not None:
            if 0.0 < v <= 1.0:
                return _clamp(v * 100.0)
            return _clamp(v)
    return _clamp(default)


def _strategy_universe(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    qsmr = _as_list(_as_dict(sources.get("qsmr")).get("registry"))
    if qsmr:
        return [r for r in qsmr if isinstance(r, dict)]
    islm = _as_list(_as_dict(sources.get("islm")).get("registry"))
    return [r for r in islm if isinstance(r, dict)]


def build_strategy_ranking(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    qcs = _as_dict(sources.get("qcs"))
    qcs_scores = _as_dict(qcs.get("scores") or qcs)
    cert_level = str(_as_dict(qcs.get("level") or qcs).get("level") or "")
    eqs = _as_dict(sources.get("eqs"))
    eqs_overall = _f(
        _as_dict(eqs.get("execution_score") or eqs).get("overall_execution_score")
    )
    cvf_conf = _f(
        _as_dict(_as_dict(sources.get("cvf")).get("confidence") or sources.get("cvf")).get(
            "confidence"
        )
    )
    res_overall = _f(
        _as_dict(
            _as_dict(sources.get("res")).get("reliability_score") or sources.get("res")
        ).get("overall_reliability_score")
    )

    ranked: list[dict[str, Any]] = []
    for s in _strategy_universe(ctx):
        scores = _as_dict(s.get("scores") or s.get("health"))
        overall = _score_or(
            50.0,
            scores.get("overall_strategy_score"),
            scores.get("overall_strategy_health"),
        )
        research = _score_or(45.0, scores.get("research_score"))
        validation = _score_or(45.0, scores.get("validation_score"), cvf_conf)
        risk = _score_or(50.0, scores.get("risk_score"))
        execution = _score_or(50.0, scores.get("execution_score"), eqs_overall)
        certification = _score_or(
            40.0,
            scores.get("certification_score"),
            qcs_scores.get("overall_institutional_readiness_score"),
        )
        composite = _clamp(
            overall * 0.3
            + validation * 0.2
            + risk * 0.15
            + execution * 0.15
            + certification * 0.1
            + research * 0.1
        )
        ranked.append(
            {
                "strategy_id": s.get("strategy_id") or s.get("id"),
                "strategy_name": s.get("strategy_name") or s.get("name"),
                "lifecycle": s.get("lifecycle") or s.get("lifecycle_state"),
                "status": s.get("status"),
                "certification_status": s.get("certification_status") or cert_level,
                "composite_rank_score": composite,
                "scores": {
                    "overall": overall,
                    "research": research,
                    "validation": validation,
                    "risk": risk,
                    "execution": execution,
                    "certification": certification,
                    "reliability_proxy": _score_or(50.0, res_overall),
                },
                "human_approval_required_to_act": True,
                "never_auto_allocates": True,
            }
        )
    ranked.sort(key=lambda r: r.get("composite_rank_score") or 0.0, reverse=True)
    for i, row in enumerate(ranked):
        row["rank"] = i + 1
    return ranked


def build_capital_allocation(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    """Advisory weights only — never applied automatically."""
    active = [
        r
        for r in ranked
        if str(r.get("status") or "").lower() not in {"retired"}
        and str(r.get("lifecycle") or "").lower() not in {"retired"}
    ]
    if not active:
        active = list(ranked)
    # Softmax-ish on composite
    temps = [max(0.01, (_f(r.get("composite_rank_score")) or 1.0) / 20.0) for r in active]
    exps = [math.exp(t) for t in temps]
    total = sum(exps) or 1.0
    allocations = []
    for r, e in zip(active, exps, strict=False):
        weight = round(e / total * 100.0, 2)
        allocations.append(
            {
                "strategy_id": r.get("strategy_id"),
                "strategy_name": r.get("strategy_name"),
                "recommended_weight_pct": weight,
                "rank": r.get("rank"),
                "composite_rank_score": r.get("composite_rank_score"),
                "advisory_only": True,
                "auto_applied": False,
                "requires_human_approval": True,
            }
        )
    # Normalize residual
    s = sum(a["recommended_weight_pct"] for a in allocations) or 1.0
    if allocations and abs(s - 100.0) > 0.05:
        allocations[0]["recommended_weight_pct"] = round(
            allocations[0]["recommended_weight_pct"] + (100.0 - s), 2
        )
    return {
        "allocations": allocations,
        "total_weight_pct": round(
            sum(a["recommended_weight_pct"] for a in allocations), 2
        ),
        "never_allocates_automatically": True,
        "never_rebalances_automatically": True,
        "human_approval_required": True,
    }


def build_portfolio_exposure(
    ranked: list[dict[str, Any]], allocation: dict[str, Any]
) -> dict[str, Any]:
    by_lifecycle: dict[str, float] = {}
    by_status: dict[str, float] = {}
    by_cert: dict[str, float] = {}
    weight_by_id = {
        str(a.get("strategy_id")): _f(a.get("recommended_weight_pct")) or 0.0
        for a in _as_list(allocation.get("allocations"))
    }
    for r in ranked:
        sid = str(r.get("strategy_id"))
        w = weight_by_id.get(sid, 0.0)
        lc = str(r.get("lifecycle") or "unknown")
        st = str(r.get("status") or "unknown")
        cert = str(r.get("certification_status") or "unknown")
        by_lifecycle[lc] = round(by_lifecycle.get(lc, 0.0) + w, 2)
        by_status[st] = round(by_status.get(st, 0.0) + w, 2)
        by_cert[cert] = round(by_cert.get(cert, 0.0) + w, 2)
    top = max(weight_by_id.values()) if weight_by_id else 0.0
    return {
        "by_lifecycle_pct": by_lifecycle,
        "by_status_pct": by_status,
        "by_certification_pct": by_cert,
        "largest_position_pct": top,
        "strategy_count": len(ranked),
        "concentration_flag": top >= 40.0,
        "read_only": True,
    }


def build_capacity_analysis(ranked: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    sims = _as_list(_as_dict(_as_dict(ctx.get("sources")).get("ise")).get("simulations"))
    # Capacity proxy: higher rank + more sim evidence → higher capacity headroom
    rows = []
    for r in ranked:
        score = _f(r.get("composite_rank_score")) or 0.0
        headroom = _clamp(score * 0.8 + min(20.0, len(sims) * 2))
        utilization = _clamp(100.0 - headroom + 15.0)
        rows.append(
            {
                "strategy_id": r.get("strategy_id"),
                "capacity_headroom_pct": headroom,
                "implied_utilization_pct": utilization,
                "simulation_evidence_count": len(sims),
                "advisory_only": True,
            }
        )
    avg_util = (
        round(sum(_f(x.get("implied_utilization_pct")) or 0 for x in rows) / len(rows), 2)
        if rows
        else 0.0
    )
    return {
        "strategies": rows,
        "portfolio_capacity_utilization_pct": avg_util,
        "never_allocates_automatically": True,
    }


def build_correlation_analysis(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    """Pairwise score-similarity as correlation proxy (research-only)."""
    n = len(ranked)
    matrix: list[list[float]] = []
    labels = [str(r.get("strategy_id")) for r in ranked]
    for i, a in enumerate(ranked):
        row = []
        sa = _f(_as_dict(a.get("scores")).get("overall")) or 50.0
        for j, b in enumerate(ranked):
            if i == j:
                row.append(1.0)
                continue
            sb = _f(_as_dict(b.get("scores")).get("overall")) or 50.0
            # Similarity in score space → proxy correlation 0..1
            corr = round(max(0.0, 1.0 - abs(sa - sb) / 100.0), 3)
            row.append(corr)
        matrix.append(row)
    # Average off-diagonal
    vals = []
    for i in range(n):
        for j in range(n):
            if i < j:
                vals.append(matrix[i][j])
    avg = round(sum(vals) / len(vals), 3) if vals else 0.0
    return {
        "labels": labels,
        "matrix": matrix,
        "average_pairwise_correlation": avg,
        "correlation_risk_score": _clamp(avg * 100.0),
        "note": "Score-similarity proxy — not live market correlation",
        "read_only": True,
    }


def build_diversification_analysis(
    exposure: dict[str, Any], correlation: dict[str, Any]
) -> dict[str, Any]:
    n = int(exposure.get("strategy_count") or 0)
    concentration = _f(exposure.get("largest_position_pct")) or 0.0
    corr_risk = _f(correlation.get("correlation_risk_score")) or 50.0
    # Higher n, lower concentration, lower corr → better diversification
    score = _clamp(
        min(40.0, n * 8.0) + max(0.0, 40.0 - concentration * 0.6) + max(0.0, 40.0 - corr_risk * 0.3)
    )
    return {
        "diversification_score": score,
        "strategy_count": n,
        "largest_position_pct": concentration,
        "correlation_risk_score": corr_risk,
        "by_lifecycle_pct": exposure.get("by_lifecycle_pct"),
        "by_certification_pct": exposure.get("by_certification_pct"),
        "read_only": True,
    }


def build_metrics(
    ctx: dict[str, Any],
    *,
    ranked: list[dict[str, Any]],
    allocation: dict[str, Any],
    diversification: dict[str, Any],
    correlation: dict[str, Any],
    capacity: dict[str, Any],
) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    irap = _as_dict(sources.get("irap"))
    metrics_src = _as_dict(irap.get("metrics") or irap)
    icp = _as_dict(sources.get("icp"))
    icp_health = _as_dict(icp.get("health") or icp)
    cvf_conf = _f(
        _as_dict(_as_dict(sources.get("cvf")).get("confidence") or sources.get("cvf")).get(
            "confidence"
        )
    )
    eqs = _f(
        _as_dict(
            _as_dict(sources.get("eqs")).get("execution_score") or sources.get("eqs")
        ).get("overall_execution_score")
    )

    # Weight-average strategy overall as expected return proxy (scaled)
    weight_by_id = {
        str(a.get("strategy_id")): (_f(a.get("recommended_weight_pct")) or 0.0) / 100.0
        for a in _as_list(allocation.get("allocations"))
    }
    exp_ret = 0.0
    for r in ranked:
        w = weight_by_id.get(str(r.get("strategy_id")), 0.0)
        exp_ret += w * ((_f(_as_dict(r.get("scores")).get("overall")) or 50.0) / 10.0)

    sharpe_raw = _f(metrics_src.get("sharpe_ratio"))
    if sharpe_raw is None:
        risk_h = _f(icp_health.get("risk_health"))
        sharpe = round((risk_h or 40.0) / 50.0, 3)
    else:
        sharpe = round(sharpe_raw, 3)

    sortino_raw = _f(metrics_src.get("sortino_ratio"))
    sortino = round(sortino_raw, 3) if sortino_raw is not None else round(sharpe * 1.15, 3)

    drawdown = _f(metrics_src.get("maximum_drawdown"))
    if drawdown is None:
        drawdown = 15.0

    capital_util = _f(capacity.get("portfolio_capacity_utilization_pct")) or 55.0
    div_score = _f(diversification.get("diversification_score")) or 50.0
    corr_risk = _f(correlation.get("correlation_risk_score")) or 50.0
    confidence = _clamp(
        (_score_or(50.0, cvf_conf) * 0.35)
        + (_score_or(50.0, eqs) * 0.25)
        + (div_score * 0.2)
        + (max(0.0, 100.0 - corr_risk) * 0.2)
    )

    metrics = {
        "portfolio_sharpe": sharpe,
        "portfolio_sortino": sortino,
        "portfolio_drawdown": round(drawdown, 2),
        "capital_utilization": round(capital_util, 2),
        "diversification_score": round(div_score, 2),
        "correlation_risk": round(corr_risk, 2),
        "expected_portfolio_return": round(exp_ret, 3),
        "portfolio_confidence_score": confidence,
    }
    return {k: metrics[k] for k in METRIC_KEYS}


def build_portfolio_health(metrics: dict[str, Any], ranked: list[dict[str, Any]]) -> dict[str, Any]:
    conf = _f(metrics.get("portfolio_confidence_score")) or 0.0
    div = _f(metrics.get("diversification_score")) or 0.0
    dd = _f(metrics.get("portfolio_drawdown")) or 0.0
    corr = _f(metrics.get("correlation_risk")) or 0.0
    overall = _clamp(
        conf * 0.35 + div * 0.25 + max(0.0, 100.0 - dd * 2.5) * 0.25 + max(0.0, 100.0 - corr) * 0.15
    )
    return {
        "overall_portfolio_health": overall,
        "strategy_count": len(ranked),
        "confidence": conf,
        "diversification": div,
        "drawdown_pressure": dd,
        "correlation_pressure": corr,
        "read_only": True,
    }


def build_portfolio_readiness(
    ctx: dict[str, Any], health: dict[str, Any], ranked: list[dict[str, Any]]
) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    qcs_level = str(
        _as_dict(_as_dict(sources.get("qcs")).get("level") or sources.get("qcs")).get(
            "level"
        )
        or "Not Ready"
    )
    certified = sum(
        1
        for r in ranked
        if "ready" in str(r.get("certification_status") or "").lower()
        or "certified" in str(r.get("certification_status") or "").lower()
        or "staging" in str(r.get("certification_status") or "").lower()
        or "production" in str(r.get("certification_status") or "").lower()
    )
    overall = _f(health.get("overall_portfolio_health")) or 0.0
    ready = overall >= 60 and certified >= 1
    return {
        "ready": ready,
        "overall_portfolio_health": overall,
        "certified_or_staging_strategies": certified,
        "platform_certification_level": qcs_level,
        "human_approval_required_for_actions": True,
        "never_rebalances_automatically": True,
        "never_allocates_capital_automatically": True,
    }


def build_recommendations(
    ranked: list[dict[str, Any]],
    metrics: dict[str, Any],
    allocation: dict[str, Any],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    weight_by_id = {
        str(a.get("strategy_id")): _f(a.get("recommended_weight_pct")) or 0.0
        for a in _as_list(allocation.get("allocations"))
    }
    dd = _f(metrics.get("portfolio_drawdown")) or 0.0
    corr = _f(metrics.get("correlation_risk")) or 0.0

    for r in ranked:
        sid = str(r.get("strategy_id"))
        score = _f(r.get("composite_rank_score")) or 0.0
        weight = weight_by_id.get(sid, 0.0)
        status = str(r.get("status") or "").lower()
        lifecycle = str(r.get("lifecycle") or "").lower()
        cert = str(r.get("certification_status") or "").lower()

        kind = None
        detail = ""
        if lifecycle in {"retired", "suspended"} or status == "retired":
            kind = "Retire strategy candidate"
            detail = f"{sid} lifecycle={lifecycle or status}"
        elif "not ready" in cert or score < 45:
            kind = "Research candidate"
            detail = f"{sid} score={score} cert={cert or 'unknown'}"
        elif dd >= 25 or score < 55:
            kind = "Reduce allocation"
            detail = f"{sid} weight={weight}% drawdown={dd}"
        elif score >= 75 and weight < 25 and (
            "ready" in cert
            or "staging" in cert
            or "certified" in cert
            or "production" in cert
        ):
            kind = "Increase allocation"
            detail = f"{sid} score={score} weight={weight}%"
        elif corr >= 80 and weight >= 30:
            kind = "Suspend allocation"
            detail = f"{sid} high correlation risk={corr} weight={weight}%"

        if kind:
            recs.append(
                {
                    "kind": kind,
                    "strategy_id": sid,
                    "strategy_name": r.get("strategy_name"),
                    "detail": detail,
                    "evidence": {
                        "composite_rank_score": score,
                        "recommended_weight_pct": weight,
                        "certification_status": r.get("certification_status"),
                        "portfolio_drawdown": dd,
                        "correlation_risk": corr,
                    },
                    "requires_human_approval": True,
                    "auto_applied": False,
                    "read_only": True,
                }
            )

    # Ensure kinds are from allowed set
    for rec in recs:
        if rec["kind"] not in RECOMMENDATION_KINDS:
            rec["kind"] = "Research candidate"

    # Deduplicate by strategy keeping first
    seen: set[str] = set()
    out = []
    for rec in recs:
        sid = str(rec.get("strategy_id"))
        if sid in seen:
            continue
        seen.add(sid)
        out.append(rec)
    return out


def build_reports(
    *,
    allocation: dict[str, Any],
    ranked: list[dict[str, Any]],
    exposure: dict[str, Any],
    diversification: dict[str, Any],
    metrics: dict[str, Any],
    recommendations: list[dict[str, Any]],
    health: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "portfolio_allocation_report": {
            "title": "Portfolio Allocation Report",
            "generated_at": now,
            "allocation": allocation,
            "human_approval_required": True,
        },
        "strategy_ranking_report": {
            "title": "Strategy Ranking Report",
            "generated_at": now,
            "ranked": ranked[:30],
        },
        "exposure_report": {
            "title": "Exposure Report",
            "generated_at": now,
            "exposure": exposure,
        },
        "diversification_report": {
            "title": "Diversification Report",
            "generated_at": now,
            "diversification": diversification,
        },
        "executive_portfolio_report": {
            "title": "Executive Portfolio Report",
            "generated_at": now,
            "metrics": metrics,
            "health": health,
            "readiness": readiness,
            "recommendations": recommendations[:15],
            "never_modifies_production": True,
            "never_rebalances_automatically": True,
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
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_integrity_check(
    *,
    ranked: list[dict[str, Any]],
    allocation: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(r.get("strategy_id") or "") for r in ranked]
    if any(not i for i in ids):
        issues.append("missing_strategy_id")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_strategy_ids")
    for key in METRIC_KEYS:
        if key not in metrics:
            issues.append(f"missing_metric:{key}")
    if not allocation.get("never_allocates_automatically"):
        issues.append("allocation_auto_flag_missing")
    if not allocation.get("human_approval_required"):
        issues.append("allocation_human_flag_missing")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
