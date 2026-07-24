"""CVF analytics — replay vs live, drift, regimes, confidence, alerts."""

from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime
from typing import Any

from app.domain.continuous_validation_framework.models import DRIFT_METRICS, REGIMES


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _f(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _perf(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("performance") or portfolio.get("performance"))


def _risk(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("risk") or portfolio.get("risk"))


def _behavior(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("behavior") or portfolio.get("behavior"))


def _live_metrics(ctx: dict[str, Any]) -> dict[str, Any]:
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    perf = _perf(portfolio)
    risk = _risk(portfolio)
    behavior = _behavior(portfolio)
    return {
        "win_rate": _f(perf.get("win_rate_pct") or perf.get("win_rate")),
        "profit_factor": _f(perf.get("profit_factor")),
        "expectancy": _f(perf.get("expectancy")),
        "average_rr": _f(perf.get("average_rr") or perf.get("avg_rr") or perf.get("reward_risk")),
        "drawdown": _f(risk.get("max_drawdown_pct")),
        "trade_frequency": _f(perf.get("trade_count") or portfolio.get("trade_count")),
        "holding_time": _f(
            behavior.get("average_holding_time_sec")
            or behavior.get("avg_holding_time_sec")
        ),
        "sample_size": int(perf.get("trade_count") or portfolio.get("trade_count") or 0),
    }


def _replay_baseline(ctx: dict[str, Any]) -> dict[str, Any]:
    irl = _as_dict(ctx.get("sources", {}).get("irl"))
    bench = _as_dict(irl.get("benchmark"))
    prod = _as_dict(bench.get("production_baseline") or bench.get("baseline"))
    board = _as_dict(irl.get("leaderboard"))
    rows = _as_list(board.get("rows"))
    best = rows[0] if rows and isinstance(rows[0], dict) else {}
    # Prefer research leaderboard as replay expectation; fall back to production baseline
    src = best if best else prod
    jobs = _as_list(irl.get("jobs"))
    return {
        "win_rate": _f(src.get("win_rate") or src.get("win_rate_pct") or prod.get("win_rate")),
        "profit_factor": _f(src.get("profit_factor") or prod.get("profit_factor")),
        "expectancy": _f(src.get("expectancy") or prod.get("expectancy")),
        "average_rr": _f(src.get("average_rr") or src.get("avg_rr") or prod.get("average_rr")),
        "drawdown": _f(
            src.get("maximum_drawdown_pct")
            or src.get("max_drawdown_pct")
            or prod.get("maximum_drawdown_pct")
        ),
        "trade_frequency": _f(src.get("total_trades") or src.get("trade_count") or prod.get("total_trades")),
        "holding_time": _f(src.get("avg_holding_time_sec") or prod.get("holding_time")),
        "sample_size": int(
            src.get("total_trades")
            or src.get("trade_count")
            or prod.get("total_trades")
            or 0
        ),
        "source": "irl_leaderboard" if best else "production_baseline",
        "experiment": best.get("name") or best.get("uuid"),
        "replay_jobs": len(jobs),
        "benchmark_production": prod,
    }


def _delta_pct(live: float | None, base: float | None) -> float | None:
    if live is None or base is None:
        return None
    if base == 0:
        return None
    return round(((live - base) / abs(base)) * 100.0, 2)


def build_replay_vs_live(ctx: dict[str, Any]) -> dict[str, Any]:
    live = _live_metrics(ctx)
    base = _replay_baseline(ctx)
    metrics = [
        "win_rate",
        "profit_factor",
        "expectancy",
        "average_rr",
        "drawdown",
        "trade_frequency",
        "holding_time",
    ]
    comparison = []
    for m in metrics:
        comparison.append(
            {
                "metric": m,
                "replay": base.get(m),
                "live": live.get(m),
                "delta_pct": _delta_pct(_f(live.get(m)), _f(base.get(m))),
            }
        )
    return {
        "replay_baseline": base,
        "live_observations": live,
        "comparison": comparison,
        "never_modifies_production": True,
    }


def build_strategy_drift(ctx: dict[str, Any], replay_vs_live: dict[str, Any]) -> dict[str, Any]:
    drifts: list[dict[str, Any]] = []
    by_metric = {
        r["metric"]: r for r in _as_list(replay_vs_live.get("comparison")) if isinstance(r, dict)
    }

    def _add(kind: str, metric: str, threshold: float, severity: str = "warning") -> None:
        row = by_metric.get(metric) or {}
        delta = _f(row.get("delta_pct"))
        if delta is None:
            return
        if abs(delta) >= threshold:
            drifts.append(
                {
                    "kind": kind,
                    "metric": metric,
                    "delta_pct": delta,
                    "severity": severity if abs(delta) >= threshold * 1.5 else "warning",
                    "replay": row.get("replay"),
                    "live": row.get("live"),
                    "read_only": True,
                }
            )

    _add("Win Rate drift", "win_rate", 12.0)
    _add("PF drift", "profit_factor", 15.0, "critical")
    _add("Expectancy drift", "expectancy", 20.0)
    _add("Drawdown drift", "drawdown", 25.0, "critical")

    # Risk profile / session / regime drift from portfolio + regime sources
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    behavior = _behavior(portfolio)
    sessions = _as_dict(behavior.get("session_performance"))
    if sessions:
        rates = []
        for name, body in sessions.items():
            if isinstance(body, dict):
                wr = _f(body.get("win_rate") or body.get("win_rate_pct"))
                if wr is not None:
                    rates.append((name, wr))
        if len(rates) >= 2:
            spread = max(r for _, r in rates) - min(r for _, r in rates)
            if spread >= 25:
                drifts.append(
                    {
                        "kind": "Session drift",
                        "metric": "session",
                        "delta_pct": round(spread, 2),
                        "severity": "warning",
                        "detail": {n: wr for n, wr in rates},
                        "read_only": True,
                    }
                )

    regime = _as_dict(ctx.get("sources", {}).get("regime"))
    current = _as_dict(regime.get("current"))
    hist_perf = _as_dict(current.get("historical_performance"))
    live_pf = _f(_live_metrics(ctx).get("profit_factor"))
    hist_pf = _f(hist_perf.get("profit_factor"))
    if live_pf is not None and hist_pf is not None and hist_pf > 0:
        d = _delta_pct(live_pf, hist_pf)
        if d is not None and abs(d) >= 20:
            drifts.append(
                {
                    "kind": "Regime drift",
                    "metric": "regime",
                    "delta_pct": d,
                    "severity": "warning",
                    "current_regime": current.get("current_regime")
                    or regime.get("current_regime"),
                    "read_only": True,
                }
            )

    risk = _risk(portfolio)
    if _f(risk.get("max_drawdown_pct")) is not None and _f(risk.get("ulcer_index")) is not None:
        # risk profile drift proxy: elevated ulcer vs drawdown ratio
        dd = _f(risk.get("max_drawdown_pct")) or 0
        ulcer = _f(risk.get("ulcer_index")) or 0
        if dd > 0 and ulcer / dd > 0.8 and dd >= 10:
            drifts.append(
                {
                    "kind": "Risk profile drift",
                    "metric": "risk_profile",
                    "delta_pct": round((ulcer / dd) * 100.0, 2),
                    "severity": "warning",
                    "drawdown": dd,
                    "ulcer_index": ulcer,
                    "read_only": True,
                }
            )

    covered = {d["metric"] for d in drifts}
    for m in DRIFT_METRICS:
        if m not in covered and m in by_metric:
            # still surface soft observation when delta exists but below threshold
            row = by_metric[m]
            if row.get("delta_pct") is not None:
                drifts.append(
                    {
                        "kind": f"{m} observation",
                        "metric": m,
                        "delta_pct": row.get("delta_pct"),
                        "severity": "info",
                        "replay": row.get("replay"),
                        "live": row.get("live"),
                        "read_only": True,
                    }
                )

    return {
        "drifts": drifts,
        "drift_count": len([d for d in drifts if d.get("severity") != "info"]),
        "never_modifies_production": True,
    }


def build_regime_validation(ctx: dict[str, Any]) -> dict[str, Any]:
    regime = _as_dict(ctx.get("sources", {}).get("regime"))
    current = _as_dict(regime.get("current"))
    current_name = str(
        current.get("current_regime") or regime.get("current_regime") or "UNKNOWN"
    )
    hist = _as_dict(current.get("historical_performance"))
    live = _live_metrics(ctx)
    rows = []
    for name in REGIMES:
        # expected from history when matching; else neutral research placeholders labeled as such
        match = name.lower().replace(" ", "_") in current_name.lower().replace(" ", "_") or name.lower() in current_name.lower()
        expected_wr = _f(hist.get("win_rate")) if match else None
        expected_pf = _f(hist.get("profit_factor")) if match else None
        # IDW regime rows
        for r in _as_list(_as_dict(ctx.get("sources", {}).get("idw")).get("regimes")):
            if not isinstance(r, dict):
                continue
            if name.lower() in str(r.get("regime") or r.get("name") or "").lower():
                expected_wr = expected_wr or _f(r.get("win_rate") or r.get("expected_win_rate"))
                expected_pf = expected_pf or _f(r.get("profit_factor") or r.get("expected_pf"))
        actual_wr = live.get("win_rate") if match else None
        actual_pf = live.get("profit_factor") if match else None
        rows.append(
            {
                "regime": name,
                "is_current": match,
                "expected_win_rate": expected_wr,
                "actual_win_rate": actual_wr,
                "expected_pf": expected_pf,
                "actual_pf": actual_pf,
                "wr_delta_pct": _delta_pct(_f(actual_wr), _f(expected_wr)),
                "pf_delta_pct": _delta_pct(_f(actual_pf), _f(expected_pf)),
            }
        )
    mismatches = [
        r
        for r in rows
        if r.get("is_current")
        and (
            (r.get("pf_delta_pct") is not None and abs(float(r["pf_delta_pct"])) >= 20)
            or (r.get("wr_delta_pct") is not None and abs(float(r["wr_delta_pct"])) >= 15)
        )
    ]
    return {
        "current_regime": current_name,
        "regimes": rows,
        "mismatches": mismatches,
        "never_modifies_production": True,
    }


def build_parameter_stability(ctx: dict[str, Any]) -> dict[str, Any]:
    """Track parameter bands for research validation — never modify them."""
    aqs = _as_dict(ctx.get("sources", {}).get("aqs"))
    recs = _as_list(aqs.get("recommendations"))
    # Research-only observed bands (documentation of current research interest)
    params = {
        "quality": {"tracked_bands": [70, 75, 80, 85, 90], "stability_score": 70.0},
        "confluence": {"tracked_bands": [2, 3, 4, 5], "stability_score": 68.0},
        "atr": {"tracked_bands": ["low", "mid", "high"], "stability_score": 65.0},
        "spread": {"tracked_bands": ["tight", "normal", "wide"], "stability_score": 72.0},
        "sessions": {
            "tracked_bands": ["tokyo", "london", "new_york", "overlap"],
            "stability_score": 66.0,
        },
        "risk_utilization": {
            "tracked_bands": ["conservative", "standard", "aggressive"],
            "stability_score": 70.0,
        },
    }
    # Adjust stability from AQS recommendation confidence if present
    confs = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        c = _f(_as_dict(r.get("scores")).get("research_confidence_score") or r.get("confidence"))
        if c is not None:
            confs.append(c)
    if confs:
        avg = statistics.mean(confs)
        for key in params:
            params[key]["stability_score"] = round(
                (params[key]["stability_score"] + avg) / 2.0, 1
            )
    return {
        "parameters": params,
        "never_changes_thresholds": True,
        "never_modifies_production": True,
        "note": "Parameter stability is observational research only",
    }


def build_statistical_confidence(
    ctx: dict[str, Any],
    *,
    replay_vs_live: dict[str, Any],
    drift: dict[str, Any],
    parameter_stability: dict[str, Any],
) -> dict[str, Any]:
    live = _as_dict(replay_vs_live.get("live_observations"))
    base = _as_dict(replay_vs_live.get("replay_baseline"))
    n_live = int(live.get("sample_size") or 0)
    n_base = int(base.get("sample_size") or 0)
    sample_size = n_live + n_base

    deltas = [
        abs(_f(r.get("delta_pct")) or 0.0)
        for r in _as_list(replay_vs_live.get("comparison"))
        if isinstance(r, dict) and r.get("delta_pct") is not None
    ]
    variance = round(statistics.pstdev(deltas), 3) if len(deltas) >= 2 else (round(deltas[0], 3) if deltas else 0.0)

    # Confidence grows with sample size, shrinks with variance and hard drifts
    sample_factor = min(100.0, math.sqrt(max(sample_size, 1)) * 8.0)
    variance_penalty = min(40.0, variance * 0.8)
    drift_penalty = min(30.0, int(drift.get("drift_count") or 0) * 6.0)
    confidence = round(max(0.0, min(100.0, sample_factor - variance_penalty - drift_penalty + 20)), 1)

    stab_vals = [
        _f(_as_dict(v).get("stability_score"))
        for v in _as_dict(parameter_stability.get("parameters")).values()
    ]
    stability_score = round(
        statistics.mean([v for v in stab_vals if v is not None]), 1
    ) if any(v is not None for v in stab_vals) else 60.0

    reliability = round(
        max(
            0.0,
            min(
                100.0,
                confidence * 0.5
                + stability_score * 0.3
                + (100.0 - min(variance, 50)) * 0.2,
            ),
        ),
        1,
    )
    evidence_score = round(
        max(
            0.0,
            min(
                100.0,
                (40 if n_base else 10)
                + (40 if n_live else 10)
                + (20 if ctx.get("availability", {}).get("irl") else 0),
            ),
        ),
        1,
    )
    return {
        "confidence": confidence,
        "sample_size": sample_size,
        "live_sample_size": n_live,
        "replay_sample_size": n_base,
        "variance": variance,
        "stability_score": stability_score,
        "reliability_score": reliability,
        "evidence_score": evidence_score,
        "never_modifies_production": True,
    }


def build_validation_alerts(
    ctx: dict[str, Any],
    *,
    drift: dict[str, Any],
    regime_validation: dict[str, Any],
    confidence: dict[str, Any],
    replay_vs_live: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for d in _as_list(drift.get("drifts")):
        if not isinstance(d, dict) or d.get("severity") == "info":
            continue
        alerts.append(
            {
                "kind": "Performance drift",
                "subtype": d.get("kind"),
                "severity": d.get("severity") or "warning",
                "detail": f"{d.get('kind')}: delta {d.get('delta_pct')}%",
                "read_only": True,
                "never_triggers_automation": True,
            }
        )

    live = _as_dict(replay_vs_live.get("live_observations"))
    base = _as_dict(replay_vs_live.get("replay_baseline"))
    live_dd = _f(live.get("drawdown"))
    base_dd = _f(base.get("drawdown"))
    if live_dd is not None and (
        (base_dd is not None and live_dd > base_dd * 1.35) or live_dd >= 15
    ):
        alerts.append(
            {
                "kind": "Unexpected drawdown",
                "severity": "critical" if live_dd >= 20 else "warning",
                "detail": f"Live drawdown {live_dd}% vs baseline {base_dd}",
                "read_only": True,
                "never_triggers_automation": True,
            }
        )

    eqs = _as_dict(ctx.get("sources", {}).get("eqs"))
    score = _as_dict(eqs.get("execution_score") or eqs)
    lat = _f(score.get("latency") or _as_dict(eqs.get("execution_score")).get("latency"))
    overall_eq = _f(score.get("overall_execution_score"))
    if lat is not None and lat < 55:
        alerts.append(
            {
                "kind": "Unexpected latency",
                "severity": "warning",
                "detail": f"EQS latency score {lat}",
                "read_only": True,
                "never_triggers_automation": True,
            }
        )
    if overall_eq is not None and overall_eq < 60:
        alerts.append(
            {
                "kind": "Execution degradation",
                "severity": "warning",
                "detail": f"EQS overall score {overall_eq}",
                "read_only": True,
                "never_triggers_automation": True,
            }
        )

    for m in _as_list(regime_validation.get("mismatches")):
        if isinstance(m, dict):
            alerts.append(
                {
                    "kind": "Regime mismatch",
                    "severity": "warning",
                    "detail": (
                        f"{m.get('regime')}: PF delta {m.get('pf_delta_pct')}%, "
                        f"WR delta {m.get('wr_delta_pct')}%"
                    ),
                    "read_only": True,
                    "never_triggers_automation": True,
                }
            )

    if (_f(confidence.get("confidence")) or 100) < 45:
        alerts.append(
            {
                "kind": "Low confidence",
                "severity": "warning",
                "detail": f"Statistical confidence {confidence.get('confidence')}",
                "read_only": True,
                "never_triggers_automation": True,
            }
        )

    for a in alerts:
        a["generated_at"] = datetime.now(UTC).isoformat()
    return alerts


def build_evidence_chains(
    ctx: dict[str, Any],
    *,
    alerts: list[dict[str, Any]],
    replay_vs_live: dict[str, Any],
    confidence: dict[str, Any],
) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    irl = _as_dict(sources.get("irl"))
    aqs = _as_dict(sources.get("aqs"))
    qkg = _as_dict(sources.get("qkg"))
    chains = []
    for alert in alerts:
        chains.append(
            {
                "alert": alert,
                "historical_baseline": replay_vs_live.get("replay_baseline"),
                "current_observations": replay_vs_live.get("live_observations"),
                "supporting_statistics": confidence,
                "related_replay": {
                    "jobs": _as_list(irl.get("jobs"))[:5],
                    "leaderboard": _as_list(_as_dict(irl.get("leaderboard")).get("rows"))[:3],
                },
                "related_research": {
                    "recommendations": _as_list(aqs.get("recommendations"))[:5],
                    "reports": _as_list(aqs.get("reports"))[:3],
                },
                "knowledge_graph_links": {
                    "stats": qkg.get("stats") or qkg,
                    "hint": "GET /qkg/search?q=validation",
                },
                "never_modifies_production": True,
            }
        )
    if not chains:
        chains.append(
            {
                "alert": None,
                "historical_baseline": replay_vs_live.get("replay_baseline"),
                "current_observations": replay_vs_live.get("live_observations"),
                "supporting_statistics": confidence,
                "related_replay": {"jobs": _as_list(irl.get("jobs"))[:5]},
                "related_research": {
                    "recommendations": _as_list(aqs.get("recommendations"))[:5]
                },
                "knowledge_graph_links": {"stats": qkg.get("stats") or qkg},
                "never_modifies_production": True,
            }
        )
    return chains


def build_executive_reports(
    *,
    replay_vs_live: dict[str, Any],
    drift: dict[str, Any],
    regime_validation: dict[str, Any],
    confidence: dict[str, Any],
    alerts: list[dict[str, Any]],
    evidence_chains: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = [d.get("kind") for d in _as_list(drift.get("drifts")) if d.get("severity") != "info"]
    findings += [a.get("kind") for a in alerts]
    recommendations = [
        "Human review required — CVF never approves promotions or changes thresholds.",
        "Investigate drifts with absolute delta ≥ threshold using evidence chains.",
        "Confirm regime mismatches against Market Regime Intelligence before action.",
    ]
    base = {
        "summary": (
            f"CVF confidence={confidence.get('confidence')}; "
            f"drift_count={drift.get('drift_count')}; alerts={len(alerts)}"
        ),
        "findings": findings[:20],
        "evidence": evidence_chains[:5],
        "recommendations": recommendations,
        "confidence": confidence,
        "replay_vs_live": replay_vs_live,
        "regime_validation": {
            "current_regime": regime_validation.get("current_regime"),
            "mismatches": regime_validation.get("mismatches"),
        },
        "advisory_only": True,
        "humans_remain_responsible": True,
    }
    return {
        "daily": {**base, "period": "daily", "title": "Daily Validation Report"},
        "weekly": {**base, "period": "weekly", "title": "Weekly Validation Report"},
        "monthly": {**base, "period": "monthly", "title": "Monthly Validation Report"},
        "quarterly": {
            **base,
            "period": "quarterly",
            "title": "Quarterly Validation Report",
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
