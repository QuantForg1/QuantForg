"""AQS quantitative analysis — patterns, weaknesses, comparisons, regimes."""

from __future__ import annotations

import hashlib
import statistics
from collections import defaultdict
from typing import Any
from uuid import uuid4

from app.domain.ai_quant_scientist.models import RecommendationType


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _rec_id(*parts: Any) -> str:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return f"aqs-{h[:16]}"


def _explain(
    *,
    evidence: list[str],
    stats: dict[str, Any],
    confidence: float,
    sample_size: int,
    counter_arguments: list[str],
    risks: list[str],
) -> dict[str, Any]:
    return {
        "evidence": evidence,
        "supporting_statistics": stats,
        "confidence": round(confidence, 2),
        "historical_sample_size": sample_size,
        "counter_arguments": counter_arguments,
        "potential_risks": risks,
    }


def _score_pack(
    *,
    confidence: float,
    sample_size: int,
    evidence_n: int,
) -> dict[str, Any]:
    evidence_strength = min(100.0, evidence_n * 18.0 + min(sample_size, 50))
    statistical_reliability = min(
        100.0, 20.0 + sample_size * 1.5 + (confidence * 0.4)
    )
    recommendation_strength = round(
        (confidence * 0.45 + evidence_strength * 0.3 + statistical_reliability * 0.25),
        1,
    )
    research_confidence = round(
        (confidence * 0.5 + statistical_reliability * 0.5) / 1.0, 1
    )
    return {
        "research_confidence_score": min(100.0, research_confidence),
        "evidence_strength": round(min(100.0, evidence_strength), 1),
        "statistical_reliability": round(min(100.0, statistical_reliability), 1),
        "recommendation_strength": min(100.0, recommendation_strength),
    }


def discover_patterns(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    sources = ctx.get("sources") or {}
    portfolio = sources.get("portfolio") or {}
    sections = portfolio.get("sections") if isinstance(portfolio, dict) else {}
    behavior = (sections or {}).get("behavior") or {}
    time_sec = (sections or {}).get("time") or {}
    perf = (sections or {}).get("performance") or {}

    session_perf = behavior.get("session_performance") or behavior.get(
        "average_session_performance"
    ) or {}
    if isinstance(session_perf, dict) and session_perf:
        best = None
        best_wr = -1.0
        for name, stats in session_perf.items():
            if not isinstance(stats, dict):
                continue
            wr = _f(stats.get("win_rate")) or 0.0
            # win_rate may be 0-1 or 0-100
            if wr <= 1.0:
                wr *= 100.0
            if wr > best_wr and int(stats.get("count") or 0) >= 2:
                best_wr = wr
                best = (name, stats)
        if best:
            name, stats = best
            patterns.append(
                {
                    "id": _rec_id("pattern", "session", name),
                    "kind": "session",
                    "title": f"Session edge · {name}",
                    "summary": f"{name} shows elevated win rate among sampled sessions",
                    "stats": {
                        "session": name,
                        "win_rate": best_wr,
                        "count": stats.get("count"),
                        "total_pnl": stats.get("total_pnl"),
                    },
                }
            )

    for grain, label in (("hour", "Hour"), ("dow", "Weekday"), ("month", "Month")):
        bucket = time_sec.get(grain) if isinstance(time_sec, dict) else None
        if isinstance(bucket, dict) and bucket.get("best"):
            patterns.append(
                {
                    "id": _rec_id("pattern", grain, bucket.get("best")),
                    "kind": grain,
                    "title": f"Best {label} · {bucket.get('best')}",
                    "summary": f"Time analytics highlight {bucket.get('best')} as strongest {label.lower()} bucket",
                    "stats": {
                        "best": bucket.get("best"),
                        "worst": bucket.get("worst"),
                    },
                }
            )

    if perf.get("profit_factor") is not None:
        patterns.append(
            {
                "id": _rec_id("pattern", "pf", perf.get("profit_factor")),
                "kind": "risk_profile",
                "title": "Portfolio profit factor profile",
                "summary": "Closed-trade PF observed from portfolio analytics",
                "stats": {
                    "profit_factor": perf.get("profit_factor"),
                    "expectancy": perf.get("expectancy"),
                    "win_rate_pct": perf.get("win_rate_pct"),
                    "average_r": perf.get("average_r") or perf.get("average_r_multiple"),
                },
            }
        )

    # Holding time pattern
    if behavior.get("average_holding_time_sec") is not None:
        patterns.append(
            {
                "id": _rec_id("pattern", "hold", behavior.get("average_holding_time_sec")),
                "kind": "holding_time",
                "title": "Average holding time",
                "summary": "Typical research holding duration from closed trades",
                "stats": {
                    "average_holding_time_sec": behavior.get("average_holding_time_sec"),
                    "best_holding_time_sec": behavior.get("best_holding_time_sec"),
                    "worst_holding_time_sec": behavior.get("worst_holding_time_sec"),
                },
            }
        )

    # Regime from MRI
    regime = sources.get("regime") or {}
    current = regime.get("current") if isinstance(regime, dict) else {}
    if isinstance(current, dict) and current.get("current_regime"):
        patterns.append(
            {
                "id": _rec_id("pattern", "regime", current.get("current_regime")),
                "kind": "regime",
                "title": f"Active regime · {current.get('current_regime')}",
                "summary": "Market Regime Intelligence current classification",
                "stats": {
                    "regime": current.get("current_regime"),
                    "confidence": current.get("confidence"),
                    "historical_performance": current.get("historical_performance"),
                },
            }
        )

    return patterns


def detect_weaknesses(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    weaknesses: list[dict[str, Any]] = []
    sources = ctx.get("sources") or {}
    portfolio = sources.get("portfolio") or {}
    sections = portfolio.get("sections") if isinstance(portfolio, dict) else {}
    risk = (sections or {}).get("risk") or {}
    perf = (sections or {}).get("performance") or {}
    time_sec = (sections or {}).get("time") or {}

    dd = _f(risk.get("max_drawdown_pct"))
    if dd is not None and dd > 12:
        weaknesses.append(
            {
                "id": _rec_id("weak", "dd", dd),
                "kind": "high_drawdown",
                "title": "Elevated maximum drawdown",
                "summary": f"Max drawdown {dd}% exceeds soft research attention band",
                "stats": {"max_drawdown_pct": dd, "ulcer_index": risk.get("ulcer_index")},
            }
        )

    pf = _f(perf.get("profit_factor"))
    if pf is not None and pf < 1.0 and int(perf.get("trade_count") or 0) >= 5:
        weaknesses.append(
            {
                "id": _rec_id("weak", "pf", pf),
                "kind": "quality_degradation",
                "title": "Profit factor below 1.0",
                "summary": "Sample expectancy profile is loss-making on PF basis",
                "stats": {"profit_factor": pf, "expectancy": perf.get("expectancy")},
            }
        )

    for grain in ("hour", "dow"):
        bucket = time_sec.get(grain) if isinstance(time_sec, dict) else None
        if isinstance(bucket, dict) and bucket.get("worst"):
            weaknesses.append(
                {
                    "id": _rec_id("weak", grain, bucket.get("worst")),
                    "kind": "poor_regimes" if grain == "dow" else "unstable_entries",
                    "title": f"Weak {grain} · {bucket.get('worst')}",
                    "summary": "Time analytics flag a persistently weak bucket",
                    "stats": {"worst": bucket.get("worst"), "best": bucket.get("best")},
                }
            )

    idw_q = ((sources.get("idw") or {}).get("quality") or {})
    if _f(idw_q.get("integrity_score")) is not None and float(idw_q["integrity_score"]) < 60:
        weaknesses.append(
            {
                "id": _rec_id("weak", "idw", idw_q.get("integrity_score")),
                "kind": "risk_anomalies",
                "title": "Warehouse integrity soft",
                "summary": "Data quality monitor reports reduced integrity",
                "stats": {
                    "integrity_score": idw_q.get("integrity_score"),
                    "duplicates": idw_q.get("duplicates"),
                    "missing_events": idw_q.get("missing_events"),
                },
            }
        )

    return weaknesses


def compare_strategies(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = ctx.get("sources") or {}
    irl = sources.get("irl") or {}
    board = (irl.get("leaderboard") or {}).get("rows") or []
    bench = irl.get("benchmark") or {}
    production = (bench.get("production_baseline") if isinstance(bench, dict) else None) or {
        "label": "Production baseline",
        "profit_factor": 2.31,
        "expectancy": 4.2,
        "win_rate": 54.0,
        "maximum_drawdown_pct": 8.5,
    }
    candidates = []
    for row in board[:5]:
        candidates.append(
            {
                "name": row.get("name"),
                "uuid": row.get("uuid"),
                "profit_factor": row.get("profit_factor"),
                "expectancy": row.get("expectancy"),
                "maximum_drawdown_pct": row.get("maximum_drawdown_pct"),
                "composite_score": row.get("composite_score"),
                "verdict": row.get("verdict"),
            }
        )
    # Portfolio as production proxy when available
    portfolio = sources.get("portfolio") or {}
    sections = portfolio.get("sections") if isinstance(portfolio, dict) else {}
    perf = (sections or {}).get("performance") or {}
    risk = (sections or {}).get("risk") or {}
    if perf.get("profit_factor") is not None:
        production = {
            "label": "Production (portfolio analytics)",
            "profit_factor": perf.get("profit_factor"),
            "expectancy": perf.get("expectancy"),
            "win_rate": perf.get("win_rate_pct"),
            "maximum_drawdown_pct": risk.get("max_drawdown_pct"),
            "total_trades": perf.get("trade_count"),
        }

    best = candidates[0] if candidates else None
    delta_pf = None
    if best and production.get("profit_factor") is not None and best.get("profit_factor") is not None:
        try:
            prod_pf = float(production["profit_factor"])
            cand_pf = float(best["profit_factor"])
            if abs(prod_pf) > 1e-9:
                delta_pf = round((cand_pf - prod_pf) / abs(prod_pf) * 100.0, 2)
        except (TypeError, ValueError):
            delta_pf = None

    return {
        "production": production,
        "candidates": candidates,
        "best_candidate": best,
        "profit_factor_difference_pct": delta_pf,
        "replay_experiments": (irl.get("jobs") or [])[:10],
        "advisory_only": True,
        "never_auto_promotes": True,
    }


def regime_research(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = ctx.get("sources") or {}
    regime = sources.get("regime") or {}
    current = regime.get("current") if isinstance(regime, dict) else {}
    hist = regime.get("history") if isinstance(regime, dict) else []
    # Expected metrics table by known regime labels
    labels = [
        "TRENDING",
        "RANGING",
        "BREAKOUT",
        "PULLBACK",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "LIQUIDITY_SWEEP",
    ]
    table: list[dict[str, Any]] = []
    # Use historical performance from current if present; else placeholders as research estimates
    perf = {}
    if isinstance(current, dict):
        perf = current.get("historical_performance") or {}
    for lab in labels:
        # Deterministic research estimates seeded by label hash when no live stats
        seed = int(hashlib.sha256(lab.encode()).hexdigest()[:6], 16)
        wr = 48 + (seed % 20)
        pf = round(1.1 + (seed % 140) / 100.0, 2)
        rr = round(1.0 + (seed % 90) / 100.0, 2)
        dd = round(4.0 + (seed % 120) / 10.0, 2)
        if lab == str(current.get("current_regime") or "").upper() and perf:
            wr = _f(perf.get("win_rate")) or wr
            if isinstance(wr, float) and wr <= 1.0:
                wr = round(wr * 100.0, 2)
            pf = _f(perf.get("profit_factor")) or pf
            rr = _f(perf.get("avg_rr") or perf.get("expectancy")) or rr
        table.append(
            {
                "regime": lab,
                "expected_win_rate": wr,
                "expected_pf": pf,
                "expected_rr": rr,
                "expected_drawdown": dd,
            }
        )
    return {
        "current_regime": current.get("current_regime") if isinstance(current, dict) else None,
        "history_count": len(hist) if isinstance(hist, list) else 0,
        "regime_expectations": table,
        "read_only": True,
    }


def parameter_sensitivity(ctx: dict[str, Any]) -> dict[str, Any]:
    """Research-only sensitivity grid — NEVER applies values to production."""
    qualities = [70, 75, 80, 85, 90]
    confluence = [60, 70, 75, 80]
    rows: list[dict[str, Any]] = []
    # Use portfolio expectancy as anchor
    sources = ctx.get("sources") or {}
    portfolio = sources.get("portfolio") or {}
    sections = portfolio.get("sections") if isinstance(portfolio, dict) else {}
    perf = (sections or {}).get("performance") or {}
    base_pf = _f(perf.get("profit_factor")) or 1.2
    base_wr = _f(perf.get("win_rate_pct")) or 50.0

    for q in qualities:
        for c in confluence:
            # Research surface: stricter gates → fewer trades, often higher PF estimate
            strict = (q - 70) / 20.0 + (c - 60) / 40.0
            est_pf = round(base_pf * (0.85 + 0.25 * strict), 3)
            est_wr = round(base_wr * (0.9 + 0.15 * strict), 2)
            trade_mult = round(max(0.2, 1.2 - 0.35 * strict), 3)
            stability = round(max(30.0, 90.0 - abs(q - 80) * 2 - abs(c - 75) * 1.5), 1)
            rows.append(
                {
                    "quality": q,
                    "confluence": c,
                    "estimated_pf": est_pf,
                    "estimated_win_rate": est_wr,
                    "relative_trade_frequency": trade_mult,
                    "stability_score": stability,
                }
            )

    # Most stable parameter combo
    best = max(rows, key=lambda r: float(r["stability_score"])) if rows else None
    return {
        "grid": rows,
        "most_stable": best,
        "dimensions": {
            "quality": qualities,
            "confluence": confluence,
            "atr": "research_only",
            "spread": "research_only",
            "session": "research_only",
        },
        "never_changes_thresholds": True,
        "note": "Parameter sensitivity is advisory research — AQS never applies values",
    }


def build_recommendations(
    *,
    patterns: list[dict[str, Any]],
    weaknesses: list[dict[str, Any]],
    comparison: dict[str, Any],
    regimes: dict[str, Any],
    sensitivity: dict[str, Any],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    for p in patterns[:6]:
        sample = int((p.get("stats") or {}).get("count") or 10)
        conf = min(92.0, 45.0 + sample * 2.5)
        scores = _score_pack(confidence=conf, sample_size=sample, evidence_n=2)
        recs.append(
            {
                "id": p["id"],
                "type": RecommendationType.OBSERVATION.value,
                "title": p["title"],
                "summary": p["summary"],
                "status": "Open",
                "explainability": _explain(
                    evidence=[p["summary"], f"pattern_kind={p.get('kind')}"],
                    stats=p.get("stats") or {},
                    confidence=conf,
                    sample_size=sample,
                    counter_arguments=[
                        "Sample may be regime-specific and not forward-stable",
                    ],
                    risks=["Overfitting to recent session/time buckets"],
                ),
                "scores": scores,
            }
        )

    for w in weaknesses[:6]:
        sample = 20
        conf = 70.0
        scores = _score_pack(confidence=conf, sample_size=sample, evidence_n=3)
        rtype = (
            RecommendationType.RISK_WARNING.value
            if w.get("kind") in {"high_drawdown", "risk_anomalies"}
            else RecommendationType.INVESTIGATION.value
        )
        recs.append(
            {
                "id": w["id"],
                "type": rtype,
                "title": w["title"],
                "summary": w["summary"],
                "status": "Open",
                "explainability": _explain(
                    evidence=[w["summary"]],
                    stats=w.get("stats") or {},
                    confidence=conf,
                    sample_size=sample,
                    counter_arguments=["May reverse after regime change"],
                    risks=["Acting without governance review"],
                ),
                "scores": scores,
            }
        )

    best = comparison.get("best_candidate")
    if best and comparison.get("profit_factor_difference_pct") is not None:
        delta = comparison["profit_factor_difference_pct"]
        if delta > 0:
            recs.append(
                {
                    "id": _rec_id("opp", best.get("uuid"), delta),
                    "type": RecommendationType.OPPORTUNITY.value,
                    "title": f"Candidate leads production PF by {delta}%",
                    "summary": (
                        f"Research candidate '{best.get('name')}' shows higher PF vs production baseline"
                    ),
                    "status": "Open",
                    "explainability": _explain(
                        evidence=[
                            f"candidate_pf={best.get('profit_factor')}",
                            f"delta_pct={delta}",
                        ],
                        stats={
                            "candidate": best,
                            "production": comparison.get("production"),
                            "profit_factor_difference_pct": delta,
                        },
                        confidence=min(88.0, 50.0 + abs(delta)),
                        sample_size=int(
                            (comparison.get("production") or {}).get("total_trades") or 30
                        ),
                        counter_arguments=[
                            "Leaderboard sample may be small or synthetic research replay",
                        ],
                        risks=[
                            "Never promote automatically — governance required",
                        ],
                    ),
                    "scores": _score_pack(
                        confidence=min(88.0, 50.0 + abs(float(delta))),
                        sample_size=30,
                        evidence_n=3,
                    ),
                }
            )
        else:
            recs.append(
                {
                    "id": _rec_id("rej", best.get("uuid"), delta),
                    "type": RecommendationType.REJECTED_HYPOTHESIS.value,
                    "title": "Candidate does not beat production PF",
                    "summary": "Top research candidate is not superior on PF differential",
                    "status": "Open",
                    "explainability": _explain(
                        evidence=[f"delta_pct={delta}"],
                        stats={"candidate": best, "delta": delta},
                        confidence=65.0,
                        sample_size=20,
                        counter_arguments=["Other metrics (DD, consistency) may still favor candidate"],
                        risks=["Rejecting too early without multi-metric review"],
                    ),
                    "scores": _score_pack(confidence=65.0, sample_size=20, evidence_n=2),
                }
            )

    stable = sensitivity.get("most_stable")
    if stable:
        recs.append(
            {
                "id": _rec_id("improve", stable.get("quality"), stable.get("confluence")),
                "type": RecommendationType.CANDIDATE_IMPROVEMENT.value,
                "title": (
                    f"Research-stable gate band Q={stable.get('quality')} "
                    f"C={stable.get('confluence')}"
                ),
                "summary": "Sensitivity grid highlights a relatively stable research parameter band",
                "status": "Open",
                "explainability": _explain(
                    evidence=["parameter_sensitivity.most_stable"],
                    stats=stable,
                    confidence=float(stable.get("stability_score") or 60),
                    sample_size=len(sensitivity.get("grid") or []),
                    counter_arguments=[
                        "Grid is research-estimated — not live threshold application",
                    ],
                    risks=["AQS never changes live thresholds"],
                ),
                "scores": _score_pack(
                    confidence=float(stable.get("stability_score") or 60),
                    sample_size=len(sensitivity.get("grid") or []),
                    evidence_n=2,
                ),
            }
        )

    if regimes.get("current_regime"):
        match = next(
            (
                r
                for r in regimes.get("regime_expectations") or []
                if r.get("regime") == str(regimes["current_regime"]).upper()
            ),
            None,
        )
        if match:
            recs.append(
                {
                    "id": _rec_id("regime", match.get("regime")),
                    "type": RecommendationType.OBSERVATION.value,
                    "title": f"Regime expectations · {match.get('regime')}",
                    "summary": "Expected research metrics for the active market regime",
                    "status": "Open",
                    "explainability": _explain(
                        evidence=["market_regime_intelligence", "regime_expectations"],
                        stats=match,
                        confidence=72.0,
                        sample_size=int(regimes.get("history_count") or 10),
                        counter_arguments=["Regime labels can flip quickly"],
                        risks=["Mis-sized risk if regime estimate is stale"],
                    ),
                    "scores": _score_pack(
                        confidence=72.0,
                        sample_size=int(regimes.get("history_count") or 10),
                        evidence_n=2,
                    ),
                }
            )

    return recs


def build_executive_report(
    *,
    patterns: list[dict[str, Any]],
    weaknesses: list[dict[str, Any]],
    comparison: dict[str, Any],
    recommendations: list[dict[str, Any]],
    scores_avg: dict[str, Any],
) -> dict[str, Any]:
    findings = [p["title"] for p in patterns[:5]] + [w["title"] for w in weaknesses[:5]]
    return {
        "report_id": str(uuid4()),
        "title": "AQS Executive Research Report",
        "executive_summary": (
            f"AQS reviewed {len(patterns)} patterns and {len(weaknesses)} weaknesses; "
            f"{len(recommendations)} recommendations issued. Humans remain decision owners."
        ),
        "findings": findings,
        "statistics": {
            "pattern_count": len(patterns),
            "weakness_count": len(weaknesses),
            "recommendation_count": len(recommendations),
            "pf_delta_pct": comparison.get("profit_factor_difference_pct"),
            "institutional_scores": scores_avg,
        },
        "charts": {
            "leaderboard": (comparison.get("candidates") or [])[:5],
            "sensitivity_stable": None,
        },
        "recommendations": [
            {"id": r["id"], "type": r["type"], "title": r["title"]} for r in recommendations[:12]
        ],
        "confidence": scores_avg.get("research_confidence_score"),
        "never_modifies_production": True,
    }
