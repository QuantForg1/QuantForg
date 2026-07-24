"""IEP analytics — lifecycle, statistics, comparison, reports (advisory)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_experimentation_platform.models import (
    LIFECYCLE_ORDER,
    VARIANT_LABELS,
    ExperimentLifecycle,
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
    return round(max(lo, min(hi, n)), 4)


def infer_lifecycle(evidence: dict[str, Any]) -> str:
    if evidence.get("archived"):
        return ExperimentLifecycle.ARCHIVE.value
    if evidence.get("human_decision_pending") or evidence.get("ai_findings"):
        if evidence.get("human_decision_recorded"):
            return ExperimentLifecycle.ARCHIVE.value
        if evidence.get("awaiting_human"):
            return ExperimentLifecycle.HUMAN_DECISION.value
        if evidence.get("ai_findings"):
            return ExperimentLifecycle.AI_REVIEW.value
    if evidence.get("statistics"):
        return ExperimentLifecycle.STATISTICAL_VALIDATION.value
    if evidence.get("irap_results"):
        return ExperimentLifecycle.RISK_ANALYSIS.value
    if evidence.get("simulation_results"):
        return ExperimentLifecycle.SIMULATION.value
    if evidence.get("replay_results"):
        return ExperimentLifecycle.REPLAY.value
    if evidence.get("variables") or evidence.get("control_group"):
        return ExperimentLifecycle.EXPERIMENT_DESIGN.value
    if evidence.get("hypothesis"):
        return ExperimentLifecycle.HYPOTHESIS.value
    return ExperimentLifecycle.IDEA.value


def compute_experiment_statistics(
    *,
    sample_size: int,
    baseline_metric: float | None,
    variant_metric: float | None,
    baseline_sd: float | None = None,
    variant_sd: float | None = None,
) -> dict[str, Any]:
    """Research-grade approximate stats — never applied to production."""
    n = max(0, int(sample_size))
    b = baseline_metric if baseline_metric is not None else 0.0
    v = variant_metric if variant_metric is not None else b
    sb = baseline_sd if baseline_sd is not None and baseline_sd > 0 else max(abs(b) * 0.15, 1.0)
    sv = variant_sd if variant_sd is not None and variant_sd > 0 else max(abs(v) * 0.15, 1.0)

    # Welch-ish t approximation for effect / p-value proxy
    se = math.sqrt((sb * sb + sv * sv) / max(n, 1))
    diff = v - b
    t_stat = diff / se if se > 1e-12 else 0.0
    # Two-sided normal approximation for p-value
    z = abs(t_stat)
    # erfc-based survival
    p_value = float(math.erfc(z / math.sqrt(2.0)))
    p_value = _clamp(p_value, 0.0, 1.0)

    # Cohen's d
    pooled = math.sqrt((sb * sb + sv * sv) / 2.0) if (sb + sv) > 0 else 1.0
    effect_size = round(diff / pooled, 4) if pooled > 1e-12 else 0.0

    # 95% CI for difference
    margin = 1.96 * se
    ci_low = round(diff - margin, 4)
    ci_high = round(diff + margin, 4)

    # Power proxy (two-sided alpha=0.05): Φ(|d|√(n/2) - 1.96)
    delta = abs(effect_size) * math.sqrt(max(n, 1) / 2.0)
    power = float(0.5 * math.erfc(-(delta - 1.96) / math.sqrt(2.0)))
    power = _clamp(power, 0.0, 1.0)

    # Generalization: sample + stability of effect vs noise
    gen = 40.0
    if n >= 5:
        gen += min(35.0, n * 0.8)
    gen += max(-20.0, min(20.0, (1.0 - p_value) * 25.0))
    gen -= min(15.0, abs(effect_size) * 2.0) if abs(effect_size) > 2 else 0
    generalization = _clamp(gen, 0.0, 100.0)

    return {
        "p_value": round(p_value, 6),
        "confidence_interval": {"low": ci_low, "high": ci_high, "level": 0.95},
        "effect_size": effect_size,
        "sample_size": n,
        "statistical_power": round(power, 4),
        "generalization_score": round(generalization, 2),
        "baseline_metric": b,
        "variant_metric": v,
        "difference": round(diff, 4),
        "t_stat_approx": round(t_stat, 4),
        "research_only": True,
        "never_applied_to_production": True,
    }


def _metric_from_row(row: dict[str, Any]) -> float | None:
    for key in (
        "composite",
        "score",
        "expectancy",
        "profit_factor",
        "sharpe_ratio",
        "win_rate",
        "net_profit",
    ):
        v = _f(row.get(key))
        if v is not None:
            return v
    metrics = _as_dict(row.get("metrics") or row.get("statistics"))
    for key in ("expectancy", "profit_factor", "sharpe", "sharpe_ratio", "win_rate"):
        v = _f(metrics.get(key))
        if v is not None:
            return v
    return None


def build_variants(
    *,
    baseline: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "label": VARIANT_LABELS[0],
            "role": "control",
            "source_id": baseline.get("experiment_id") or baseline.get("id") or "baseline",
            "name": baseline.get("name") or baseline.get("title") or "Baseline",
            "metric": _metric_from_row(baseline),
            "payload": {
                k: baseline.get(k)
                for k in ("status", "hypothesis", "params", "statistics")
                if k in baseline
            },
        }
    ]
    for i, cand in enumerate(candidates[:3]):
        cd = _as_dict(cand)
        rows.append(
            {
                "label": VARIANT_LABELS[min(i + 1, len(VARIANT_LABELS) - 1)],
                "role": "variant",
                "source_id": cd.get("experiment_id") or cd.get("id") or f"var-{i}",
                "name": cd.get("name") or cd.get("title") or f"Variant {chr(65 + i)}",
                "metric": _metric_from_row(cd),
                "payload": {
                    k: cd.get(k)
                    for k in ("status", "hypothesis", "params", "statistics")
                    if k in cd
                },
            }
        )
    return rows


def rank_variants(variants: list[dict[str, Any]], stats_by_label: dict[str, dict]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for v in variants:
        label = str(v.get("label"))
        st = stats_by_label.get(label) or {}
        metric = _f(v.get("metric")) or 0.0
        evidence_score = 50.0
        if st:
            # Prefer larger |effect|, higher power, lower p, higher generalization
            evidence_score = _clamp(
                (1.0 - (_f(st.get("p_value")) or 1.0)) * 35.0
                + (_f(st.get("statistical_power")) or 0.0) * 30.0
                + (_f(st.get("generalization_score")) or 0.0) * 0.25
                + abs(_f(st.get("effect_size")) or 0.0) * 10.0
                + max(0.0, metric) * 0.05
            )
        ranked.append(
            {
                **v,
                "evidence_rank_score": round(evidence_score, 2),
                "statistics": st or None,
            }
        )
    ranked.sort(key=lambda r: r.get("evidence_rank_score") or 0.0, reverse=True)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ranked


def build_registry_from_sources(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    irl = _as_dict(sources.get("irl"))
    experiments = _as_list(irl.get("experiments"))
    ise = _as_dict(sources.get("ise"))
    sims = _as_list(ise.get("simulations"))
    cvf = _as_dict(sources.get("cvf"))
    irap = _as_dict(sources.get("irap"))
    aqs = _as_dict(sources.get("aqs"))
    recs = _as_list(aqs.get("recommendations"))
    qkg = _as_dict(sources.get("qkg"))
    portfolio = _as_dict(sources.get("portfolio"))
    sections = _as_dict(portfolio.get("sections"))
    perf = _as_dict(sections.get("performance"))

    qkg_links: list[dict[str, Any]] = []
    for node in _as_list(qkg.get("nodes")):
        nd = _as_dict(node)
        label = str(nd.get("label") or nd.get("id") or "")
        ntype = str(nd.get("type") or nd.get("kind") or "").lower()
        if any(k in ntype or k in label.lower() for k in ("exper", "hypoth", "strateg", "variant")):
            qkg_links.append(
                {
                    "node_id": nd.get("id") or nd.get("node_id"),
                    "label": label,
                    "type": ntype,
                }
            )

    replay_results = [
        {
            "simulation_id": _as_dict(s).get("simulation_id") or _as_dict(s).get("id"),
            "mode": _as_dict(s).get("mode") or _as_dict(s).get("scenario"),
            "metrics": _as_dict(s).get("metrics"),
        }
        for s in sims
        if "replay" in str(_as_dict(s).get("mode") or "").lower()
        or "historical" in str(_as_dict(s).get("mode") or _as_dict(s).get("scenario") or "").lower()
    ]
    simulation_results = [
        {
            "simulation_id": _as_dict(s).get("simulation_id") or _as_dict(s).get("id"),
            "scenario": _as_dict(s).get("scenario") or _as_dict(s).get("mode"),
            "metrics": _as_dict(s).get("metrics"),
        }
        for s in sims[:20]
    ]
    cvf_results = {
        "confidence": _as_dict(cvf.get("confidence") or cvf).get("confidence"),
        "alerts": _as_list(cvf.get("alerts")),
        "observed_at": cvf.get("observed_at"),
    }
    irap_results = {
        "metrics": _as_dict(irap.get("metrics") or irap),
        "alerts": _as_list(irap.get("alerts")),
        "observed_at": irap.get("observed_at"),
    }
    ai_findings = [
        {
            "recommendation_id": _as_dict(r).get("recommendation_id") or _as_dict(r).get("id"),
            "title": _as_dict(r).get("title") or _as_dict(r).get("summary"),
            "scores": _as_dict(r).get("scores"),
        }
        for r in recs[:15]
    ]

    baseline_metric = _f(perf.get("expectancy")) or _f(perf.get("profit_factor")) or 1.0
    sample_n = int(_f(portfolio.get("trade_count")) or _f(perf.get("trade_count")) or 30)

    rows: list[dict[str, Any]] = []
    if not experiments:
        # Synthetic observational scaffold from live research evidence
        variants = build_variants(
            baseline={
                "experiment_id": "baseline-portfolio",
                "name": "Production observational baseline",
                "expectancy": baseline_metric,
            },
            candidates=[
                {
                    "experiment_id": f"obs-var-{i}",
                    "name": f"Observational {VARIANT_LABELS[i]}",
                    "expectancy": baseline_metric * (1.0 + (i - 1) * 0.05),
                }
                for i in range(1, 4)
            ],
        )
        stats_map: dict[str, dict[str, Any]] = {}
        control_m = _f(variants[0].get("metric")) or baseline_metric
        for var in variants[1:]:
            st = compute_experiment_statistics(
                sample_size=sample_n,
                baseline_metric=control_m,
                variant_metric=_f(var.get("metric")),
            )
            stats_map[str(var["label"])] = st
        ranked = rank_variants(variants, stats_map)
        primary_stats = stats_map.get("Variant A") or compute_experiment_statistics(
            sample_size=sample_n,
            baseline_metric=control_m,
            variant_metric=control_m,
        )
        evidence = {
            "hypothesis": "Observational comparison of research variants vs portfolio baseline",
            "variables": ["expectancy", "profit_factor", "drawdown"],
            "control_group": variants[0],
            "variant_groups": variants[1:],
            "replay_results": replay_results,
            "simulation_results": simulation_results,
            "cvf_results": cvf_results if cvf else {},
            "irap_results": irap_results if irap else {},
            "ai_findings": ai_findings,
            "evidence_links": [
                {"kind": "portfolio", "present": bool(portfolio)},
                {"kind": "ise", "count": len(sims)},
                {"kind": "cvf", "present": bool(cvf)},
                {"kind": "irap", "present": bool(irap)},
            ],
            "knowledge_graph_links": qkg_links[:30],
            "statistics": primary_stats,
            "awaiting_human": True,
            "archived": False,
        }
        rows.append(
            {
                "experiment_id": "iep-observational-primary",
                "title": "Primary observational experiment",
                "hypothesis": evidence["hypothesis"],
                "lifecycle_state": infer_lifecycle(evidence),
                "variables": evidence["variables"],
                "control_group": evidence["control_group"],
                "variant_groups": evidence["variant_groups"],
                "comparison": ranked,
                "statistics": primary_stats,
                "evidence": evidence,
                "recommended_decision": "hold_for_human_review",
                "never_auto_approves": True,
                "never_auto_promotes": True,
                "owner": "quantforg-research",
            }
        )
        return rows

    # Map IRL experiments
    for idx, exp in enumerate(experiments[:25]):
        ed = _as_dict(exp)
        eid = str(ed.get("experiment_id") or ed.get("id") or f"irl-{uuid4().hex[:8]}")
        peers = [ _as_dict(x) for x in experiments if _as_dict(x).get("experiment_id") != eid ][
            :3
        ]
        variants = build_variants(baseline=ed, candidates=peers)
        stats_map = {}
        control_m = _f(variants[0].get("metric")) or baseline_metric
        for var in variants[1:]:
            stats_map[str(var["label"])] = compute_experiment_statistics(
                sample_size=int(
                    _f(_as_dict(ed.get("statistics")).get("total_trades")) or sample_n
                ),
                baseline_metric=control_m,
                variant_metric=_f(var.get("metric")),
            )
        ranked = rank_variants(variants, stats_map)
        primary_stats = next(iter(stats_map.values()), None) or compute_experiment_statistics(
            sample_size=sample_n,
            baseline_metric=control_m,
            variant_metric=control_m,
        )
        hypothesis = str(
            ed.get("hypothesis")
            or ed.get("description")
            or ed.get("name")
            or f"IRL experiment {eid}"
        )
        evidence = {
            "hypothesis": hypothesis,
            "variables": list(_as_dict(ed.get("params") or ed.get("candidate_params")).keys())[
                :12
            ]
            or ["candidate_params"],
            "control_group": variants[0],
            "variant_groups": variants[1:],
            "replay_results": replay_results,
            "simulation_results": simulation_results,
            "cvf_results": cvf_results if cvf else {},
            "irap_results": irap_results if irap else {},
            "ai_findings": ai_findings,
            "evidence_links": [
                {"kind": "irl", "experiment_id": eid},
                {"kind": "ise", "count": len(sims)},
                {"kind": "cvf", "present": bool(cvf)},
                {"kind": "irap", "present": bool(irap)},
                {"kind": "aqs", "count": len(recs)},
            ],
            "knowledge_graph_links": qkg_links[:30],
            "statistics": primary_stats,
            "awaiting_human": str(ed.get("status") or "").lower()
            not in {"archived", "archive"},
            "archived": str(ed.get("status") or "").lower() in {"archived", "archive"},
            "irl_raw": {
                "status": ed.get("status"),
                "verdict": ed.get("verdict") or ed.get("research_verdict"),
            },
        }
        # Enrich lifecycle with AI / risk presence
        if ai_findings and not evidence["archived"]:
            evidence["ai_findings"] = ai_findings
        rows.append(
            {
                "experiment_id": f"iep-{eid}",
                "title": str(ed.get("name") or ed.get("title") or eid),
                "hypothesis": hypothesis,
                "lifecycle_state": infer_lifecycle(evidence),
                "variables": evidence["variables"],
                "control_group": evidence["control_group"],
                "variant_groups": evidence["variant_groups"],
                "comparison": ranked,
                "statistics": primary_stats,
                "evidence": evidence,
                "recommended_decision": "hold_for_human_review",
                "never_auto_approves": True,
                "never_auto_promotes": True,
                "owner": str(ed.get("owner") or "quantforg-research"),
                "origin": "irl",
                "source_experiment_id": eid,
                "ordinal": idx,
            }
        )
    return rows


def build_comparison_workspace(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    primary = experiments[0] if experiments else {}
    ranked = _as_list(primary.get("comparison"))
    return {
        "experiment_id": primary.get("experiment_id"),
        "baseline": next((r for r in ranked if r.get("label") == "Baseline"), None),
        "variants": [r for r in ranked if r.get("role") == "variant"],
        "ranked_by_evidence": ranked,
        "never_auto_promotes": True,
    }


def build_decision_dashboard(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    pending = [
        {
            "experiment_id": e.get("experiment_id"),
            "title": e.get("title"),
            "lifecycle_state": e.get("lifecycle_state"),
            "recommended_decision": e.get("recommended_decision"),
            "top_variant": (_as_list(e.get("comparison")) or [{}])[0],
            "requires_human": True,
            "auto_approve": False,
            "auto_promote": False,
        }
        for e in experiments
        if e.get("lifecycle_state")
        in {
            ExperimentLifecycle.AI_REVIEW.value,
            ExperimentLifecycle.HUMAN_DECISION.value,
            ExperimentLifecycle.STATISTICAL_VALIDATION.value,
        }
        or e.get("recommended_decision") == "hold_for_human_review"
    ]
    archived = [
        e
        for e in experiments
        if e.get("lifecycle_state") == ExperimentLifecycle.ARCHIVE.value
    ]
    return {
        "pending_human_decisions": pending[:30],
        "archived_count": len(archived),
        "total_experiments": len(experiments),
        "never_approves_automatically": True,
        "never_promotes_automatically": True,
        "note": "Human decision required — IEP records evidence only",
    }


def build_hypothesis_builder(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    templates = []
    for e in experiments[:10]:
        templates.append(
            {
                "experiment_id": e.get("experiment_id"),
                "hypothesis": e.get("hypothesis"),
                "variables": e.get("variables"),
                "control_group": e.get("control_group"),
                "variant_groups": e.get("variant_groups"),
                "lifecycle_state": e.get("lifecycle_state"),
                "editable_in_production": False,
                "research_scaffold_only": True,
            }
        )
    return {
        "scaffolds": templates,
        "lifecycle_states": list(LIFECYCLE_ORDER),
        "variant_labels": list(VARIANT_LABELS),
        "never_modifies_strategies": True,
    }


def build_reports(
    *,
    experiments: list[dict[str, Any]],
    comparison: dict[str, Any],
    decisions: dict[str, Any],
) -> dict[str, Any]:
    primary = experiments[0] if experiments else {}
    evidence = _as_dict(primary.get("evidence"))
    return {
        "experiment_report": {
            "title": "Experiment Report",
            "experiments": [
                {
                    "experiment_id": e.get("experiment_id"),
                    "title": e.get("title"),
                    "hypothesis": e.get("hypothesis"),
                    "lifecycle_state": e.get("lifecycle_state"),
                    "statistics": e.get("statistics"),
                }
                for e in experiments[:20]
            ],
        },
        "comparison_report": {
            "title": "Comparison Report",
            **comparison,
        },
        "evidence_report": {
            "title": "Evidence Report",
            "experiment_id": primary.get("experiment_id"),
            "evidence": evidence,
            "integrity": {
                "has_unique_ids": all(bool(e.get("experiment_id")) for e in experiments),
                "lifecycle_in_enum": all(
                    e.get("lifecycle_state") in LIFECYCLE_ORDER for e in experiments
                ),
                "statistics_keys_present": all(
                    {
                        "p_value",
                        "confidence_interval",
                        "effect_size",
                        "sample_size",
                        "statistical_power",
                        "generalization_score",
                    }.issubset(set(_as_dict(e.get("statistics")).keys()))
                    for e in experiments
                    if e.get("statistics")
                ),
            },
        },
        "decision_report": {
            "title": "Decision Report",
            **decisions,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


def statistical_consistency_check(stats: dict[str, Any]) -> dict[str, Any]:
    p = _f(stats.get("p_value"))
    power = _f(stats.get("statistical_power"))
    n = _f(stats.get("sample_size"))
    gen = _f(stats.get("generalization_score"))
    ci = _as_dict(stats.get("confidence_interval"))
    ok = True
    issues: list[str] = []
    if p is None or not (0.0 <= p <= 1.0):
        ok = False
        issues.append("p_value_out_of_range")
    if power is None or not (0.0 <= power <= 1.0):
        ok = False
        issues.append("power_out_of_range")
    if n is None or n < 0:
        ok = False
        issues.append("sample_size_invalid")
    if gen is None or not (0.0 <= gen <= 100.0):
        ok = False
        issues.append("generalization_out_of_range")
    low, high = _f(ci.get("low")), _f(ci.get("high"))
    if low is not None and high is not None and low > high:
        ok = False
        issues.append("ci_inverted")
    return {"ok": ok, "issues": issues, "research_only": True}
