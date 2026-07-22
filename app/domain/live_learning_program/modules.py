"""LLP modules — collect/organize/analyze evidence; never mutates production."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.live_learning_program.config import (
    JOURNAL_DAY_TYPES,
    OPERATOR_TAGS,
    LlpConfig,
)
from app.domain.live_learning_program.types import LlpInput, ModuleResult

INSUFFICIENT = "INSUFFICIENT EVIDENCE"
OBS_FIELDS = (
    "entry_context",
    "exit_context",
    "market_regime",
    "session",
    "spread",
    "volatility",
    "liquidity",
    "risk_usage",
    "decision_explanation",
    "execution_latency",
    "result",
)


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _insufficient(module: str, detail: str) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="insufficient_evidence",
        score=None,
        recommendation=INSUFFICIENT,
        reasons=(detail, "Never fabricates learning evidence"),
        details={"verdict": INSUFFICIENT},
    )


def live_observation_collector(
    inp: LlpInput, config: LlpConfig
) -> ModuleResult:
    trades = [t for t in (inp.completed_trades or []) if isinstance(t, dict)]
    if not trades:
        return ModuleResult(
            module="live_observation_collector",
            status="empty",
            score=None,
            recommendation="No completed trades to observe",
            reasons=(
                "Supply completed_trades with immutable observation fields",
                "Never invents trade outcomes",
            ),
            details={"observations": [], "immutable": True},
        )

    observations: list[dict[str, Any]] = []
    missing_by_field: dict[str, int] = dict.fromkeys(OBS_FIELDS, 0)
    for t in trades[: config.max_observations]:
        obs: dict[str, Any] = {
            "id": str(t.get("id") or f"obs_{uuid4().hex[:10]}"),
            "immutable": True,
            "recorded_at": str(
                t.get("recorded_at") or datetime.now(UTC).isoformat()
            ),
            "source": str(t.get("source") or "live"),
        }
        for field in OBS_FIELDS:
            # Accept aliases
            aliases = {
                "market_regime": ("regime",),
                "result": ("pnl", "net_pnl", "outcome"),
                "execution_latency": ("latency_ms", "execution_latency_ms"),
            }
            val = t.get(field)
            if val is None:
                for alt in aliases.get(field, ()):
                    if t.get(alt) is not None:
                        val = t.get(alt)
                        break
            if val is None:
                missing_by_field[field] += 1
                obs[field] = None
            else:
                obs[field] = val
        observations.append(obs)

    return ModuleResult(
        module="live_observation_collector",
        status="available",
        score=Decimal(str(len(observations))),
        recommendation=f"{len(observations)} immutable observation(s)",
        reasons=(
            "Entry/exit context, regime, session, spread, vol, liquidity, "
            "risk, decision, latency, result",
            "Observations are immutable evidence — never rewrite outcomes",
        ),
        details={
            "observations": observations,
            "observation_count": len(observations),
            "missing_field_counts": missing_by_field,
            "immutable": True,
            "never_mutates_production": True,
        },
    )


def replay_comparison(inp: LlpInput, config: LlpConfig) -> ModuleResult:
    _ = config
    replay = inp.replay_results if isinstance(inp.replay_results, dict) else None
    paper = inp.paper_results if isinstance(inp.paper_results, dict) else None
    live = inp.live_results if isinstance(inp.live_results, dict) else None
    if not replay and not paper and not live:
        return _insufficient(
            "replay_comparison",
            "Supply replay_results, paper_results, and/or live_results",
        )

    metrics = (
        "expectancy",
        "win_rate",
        "profit_factor",
        "drawdown",
        "trade_count",
        "avg_latency_ms",
    )
    sides = {"replay": replay, "paper": paper, "live": live}
    similarities: list[str] = []
    differences: list[str] = []
    unexpected: list[str] = []

    for key in metrics:
        vals: dict[str, Decimal] = {}
        for name, src in sides.items():
            if not src:
                continue
            d = _dec(src.get(key))
            if d is not None:
                vals[name] = d
        if len(vals) < 2:
            continue
        nums = list(vals.values())
        avg = sum(nums) / Decimal(len(nums))
        spread = max(nums) - min(nums)
        rel = spread if avg == 0 else abs(spread / avg)
        label = ", ".join(f"{k}={v}" for k, v in vals.items())
        if rel <= Decimal("0.15"):
            similarities.append(f"{key}: similar ({label})")
        else:
            differences.append(f"{key}: differs ({label})")
            if (
                "live" in vals
                and "replay" in vals
                and abs(vals["live"] - vals["replay"])
                > abs(avg) * Decimal("0.5")
            ):
                unexpected.append(
                    f"{key}: live diverges sharply from replay"
                )

    # Structural unexpected: live latency much worse than paper if both present
    if paper and live:
        pl = _dec(paper.get("avg_latency_ms"))
        ll = _dec(live.get("avg_latency_ms"))
        if pl is not None and ll is not None and ll > pl * Decimal("2"):
            unexpected.append("Live execution latency >> paper")

    return ModuleResult(
        module="replay_comparison",
        status="available",
        score=Decimal(str(len(similarities) + len(differences))),
        recommendation="Replay / paper / live compared from supplied metrics",
        reasons=(
            "Highlights similarities, differences, unexpected behaviour",
            "Never auto-tunes from comparison",
        ),
        details={
            "replay": replay or {},
            "paper": paper or {},
            "live": live or {},
            "similarities": similarities,
            "differences": differences,
            "unexpected_behaviour": unexpected,
            "auto_tune": False,
        },
    )


def operator_feedback(inp: LlpInput, config: LlpConfig) -> ModuleResult:
    rows = [r for r in (inp.operator_feedback or []) if isinstance(r, dict)]
    if not rows:
        return ModuleResult(
            module="operator_feedback",
            status="empty",
            score=None,
            recommendation="No operator feedback tagged",
            reasons=(
                f"Allowed tags: {', '.join(OPERATOR_TAGS)}",
                "Feedback never changes production automatically",
            ),
            details={
                "items": [],
                "allowed_tags": list(OPERATOR_TAGS),
                "changes_production": False,
            },
        )

    items: list[dict[str, Any]] = []
    by_tag: dict[str, int] = dict.fromkeys(OPERATOR_TAGS, 0)
    for r in rows[: config.max_feedback]:
        tag = str(r.get("tag") or "").strip().lower().replace(" ", "_")
        tag = tag.replace("-", "_")
        if tag not in OPERATOR_TAGS:
            continue
        by_tag[tag] += 1
        items.append(
            {
                "id": str(r.get("id") or f"fb_{uuid4().hex[:8]}"),
                "tag": tag,
                "note": str(r.get("note") or ""),
                "trade_id": r.get("trade_id"),
                "operator": str(r.get("operator") or "unknown"),
                "recorded_at": str(
                    r.get("recorded_at") or datetime.now(UTC).isoformat()
                ),
                "changes_production": False,
            }
        )

    return ModuleResult(
        module="operator_feedback",
        status="available" if items else "empty",
        score=Decimal(str(len(items))) if items else None,
        recommendation=f"{len(items)} feedback tag(s) recorded",
        reasons=(
            "Good/bad setup, late entry, early exit, execution, anomaly, idea",
            "Feedback must never change production automatically",
        ),
        details={
            "items": items,
            "by_tag": by_tag,
            "allowed_tags": list(OPERATOR_TAGS),
            "changes_production": False,
            "never_auto_applies": True,
        },
    )


def edge_evolution(inp: LlpInput, config: LlpConfig) -> ModuleResult:
    series = [
        s for s in (inp.edge_score_series or []) if isinstance(s, dict)
    ]
    # Also derive crude points from completed trades if series thin
    if len(series) < 2:
        trades = [
            t for t in (inp.completed_trades or []) if isinstance(t, dict)
        ]
        if len(trades) >= config.min_observations_for_edge:
            # Bucket by supplied period labels on trades if present
            buckets: dict[str, list[Decimal]] = defaultdict(list)
            for t in trades:
                period = str(
                    t.get("period") or t.get("bucket") or "unspecified"
                )
                pnl = _dec(t.get("result") or t.get("pnl") or t.get("net_pnl"))
                if pnl is not None:
                    buckets[period].append(pnl)
            for period, pnls in buckets.items():
                if not pnls:
                    continue
                avg = sum(pnls) / Decimal(len(pnls))
                series.append(
                    {
                        "period": period,
                        "horizon": "derived",
                        "edge_score": str(avg.quantize(Decimal("0.01"))),
                    }
                )

    if len(series) < 2:
        return _insufficient(
            "edge_evolution",
            f"Need ≥2 edge points or ≥{config.min_observations_for_edge} trades",
        )

    horizons = ("daily", "weekly", "monthly", "quarterly")
    by_horizon: dict[str, list[dict[str, Any]]] = {h: [] for h in horizons}
    points: list[dict[str, Any]] = []
    for s in series[:500]:
        score = _dec(s.get("edge_score") or s.get("score"))
        if score is None:
            continue
        horizon = str(s.get("horizon") or s.get("period_type") or "daily")
        horizon = horizon.lower()
        if horizon not in by_horizon:
            horizon = "daily"
        row = {
            "period": str(s.get("period") or s.get("label") or "n/a"),
            "horizon": horizon,
            "edge_score": str(score),
        }
        points.append(row)
        by_horizon[horizon].append(row)

    scores = [
        float(_dec(p["edge_score"]) or 0) for p in points if p.get("edge_score")
    ]
    trend = "insufficient"
    if len(scores) >= 2:
        if scores[-1] > scores[0] * 1.05:
            trend = "improving"
        elif scores[-1] < scores[0] * 0.95:
            trend = "degrading"
        else:
            trend = "stable"

    return ModuleResult(
        module="edge_evolution",
        status="available",
        score=Decimal(str(len(points))),
        recommendation=f"Edge trend: {trend}",
        reasons=(
            "Tracks daily/weekly/monthly/quarterly edge scores",
            "Detects trends only — never auto-tunes parameters",
        ),
        details={
            "points": points,
            "by_horizon": by_horizon,
            "trend": trend,
            "detects_trends_only": True,
            "auto_tune": False,
        },
    )


def market_behaviour_journal(
    inp: LlpInput, config: LlpConfig
) -> ModuleResult:
    entries = [
        e for e in (inp.journal_entries or []) if isinstance(e, dict)
    ]
    # Also harvest from observations
    for t in inp.completed_trades or []:
        if not isinstance(t, dict):
            continue
        day_type = t.get("day_type") or t.get("journal_type")
        if day_type:
            entries.append(
                {
                    "day_type": day_type,
                    "session": t.get("session"),
                    "note": t.get("journal_note") or "",
                    "date": t.get("date") or t.get("recorded_at"),
                }
            )

    if not entries:
        return ModuleResult(
            module="market_behaviour_journal",
            status="empty",
            score=None,
            recommendation="Journal empty",
            reasons=(
                f"Types: {', '.join(JOURNAL_DAY_TYPES)}",
                "Never invents market day classifications",
            ),
            details={"entries": [], "by_type": {}, "searchable": True},
        )

    normalized: list[dict[str, Any]] = []
    by_type: dict[str, list[dict[str, Any]]] = {
        k: [] for k in JOURNAL_DAY_TYPES
    }
    for e in entries[: config.max_journal]:
        raw = str(e.get("day_type") or e.get("type") or "").strip().lower()
        raw = raw.replace(" ", "_").replace("-", "_")
        aliases = {
            "trend": "trend_days",
            "range": "range_days",
            "news": "news_days",
            "high_vol": "high_volatility",
            "low_vol": "low_volatility",
            "session": "session_observations",
        }
        day_type = aliases.get(raw, raw)
        if day_type not in JOURNAL_DAY_TYPES:
            continue
        row = {
            "id": str(e.get("id") or f"j_{uuid4().hex[:8]}"),
            "day_type": day_type,
            "session": e.get("session"),
            "note": str(e.get("note") or ""),
            "date": e.get("date"),
            "searchable": True,
        }
        normalized.append(row)
        by_type[day_type].append(row)

    return ModuleResult(
        module="market_behaviour_journal",
        status="available" if normalized else "empty",
        score=Decimal(str(len(normalized))) if normalized else None,
        recommendation=f"{len(normalized)} journal entr(y/ies)",
        reasons=(
            "Trend/range/news/HV/LV/session observations — searchable",
            "Read-only learning journal",
        ),
        details={
            "entries": normalized,
            "by_type": {k: len(v) for k, v in by_type.items()},
            "search_index": [
                {
                    "id": r["id"],
                    "day_type": r["day_type"],
                    "session": r.get("session"),
                }
                for r in normalized
            ],
            "searchable": True,
        },
    )


def confidence_tracking(inp: LlpInput, config: LlpConfig) -> ModuleResult:
    pairs = [
        p for p in (inp.confidence_pairs or []) if isinstance(p, dict)
    ]
    if not pairs:
        # Derive from trades with predicted_confidence + result
        for t in inp.completed_trades or []:
            if not isinstance(t, dict):
                continue
            pred = _dec(
                t.get("predicted_confidence") or t.get("confidence")
            )
            if pred is None:
                continue
            win = t.get("win")
            if win is None:
                pnl = _dec(t.get("result") or t.get("pnl") or t.get("net_pnl"))
                if pnl is None:
                    continue
                win = pnl > 0
            pairs.append(
                {
                    "predicted_confidence": str(pred),
                    "observed_win": bool(win),
                }
            )

    if len(pairs) < config.min_observations_for_calibration:
        return _insufficient(
            "confidence_tracking",
            f"Need ≥{config.min_observations_for_calibration} "
            "predicted/observed pairs",
        )

    # Simple calibration: bucket by predicted confidence decade
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "wins": 0}
    )
    for p in pairs:
        pred = _dec(p.get("predicted_confidence") or p.get("predicted"))
        if pred is None:
            continue
        # Normalize 0-1 or 0-100
        pred_pct = float(pred * 100) if pred <= 1 else float(pred)
        bucket = f"{int(pred_pct // 10) * 10}-{int(pred_pct // 10) * 10 + 9}"
        win = p.get("observed_win")
        if win is None:
            outcome = _dec(p.get("observed_outcome") or p.get("pnl"))
            if outcome is None:
                continue
            win = outcome > 0
        buckets[bucket]["n"] += 1
        if win:
            buckets[bucket]["wins"] += 1

    calibration: list[dict[str, Any]] = []
    gaps: list[float] = []
    for bucket, stats in sorted(buckets.items()):
        n = stats["n"]
        if n == 0:
            continue
        observed = stats["wins"] / n * 100
        mid = (int(bucket.split("-")[0]) + int(bucket.split("-")[1])) / 2
        gap = abs(observed - mid)
        gaps.append(gap)
        calibration.append(
            {
                "predicted_bucket": bucket,
                "sample": n,
                "observed_win_rate_pct": round(observed, 2),
                "calibration_gap_pct": round(gap, 2),
            }
        )

    quality = "insufficient"
    if gaps:
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap <= 8:
            quality = "good"
        elif avg_gap <= 15:
            quality = "moderate"
        else:
            quality = "poor"

    return ModuleResult(
        module="confidence_tracking",
        status="available",
        score=Decimal(str(len(pairs))),
        recommendation=f"Calibration quality: {quality}",
        reasons=(
            "Compares predicted confidence vs observed outcomes",
            "Never auto-adjusts confidence thresholds",
        ),
        details={
            "pair_count": len(pairs),
            "calibration": calibration,
            "calibration_quality": quality,
            "auto_adjust": False,
        },
    )


def weekly_review(
    inp: LlpInput, modules: dict[str, ModuleResult]
) -> ModuleResult:
    _ = inp
    obs = modules.get("live_observation_collector")
    cmp_ = modules.get("replay_comparison")
    fb = modules.get("operator_feedback")
    edge = modules.get("edge_evolution")
    journal = modules.get("market_behaviour_journal")

    top_obs: list[str] = []
    if obs and obs.status == "available":
        top_obs.append(
            f"{(obs.details or {}).get('observation_count', 0)} "
            "immutable observations collected"
        )
    if fb and fb.status == "available":
        by_tag = (fb.details or {}).get("by_tag") or {}
        for tag, n in by_tag.items():
            if n:
                top_obs.append(f"Operator tag {tag}: {n}")

    unexpected: list[str] = []
    if cmp_:
        unexpected.extend(
            (cmp_.details or {}).get("unexpected_behaviour") or []
        )

    strongest: list[str] = []
    weakest: list[str] = []
    if journal and journal.status == "available":
        by_type = (journal.details or {}).get("by_type") or {}
        ranked = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        if ranked and ranked[0][1]:
            strongest.append(f"Most logged: {ranked[0][0]} ({ranked[0][1]})")
        empty = [k for k, v in by_type.items() if not v]
        if empty:
            weakest.append(f"No samples: {', '.join(empty[:3])}")
    if edge and (edge.details or {}).get("trend") == "degrading":
        weakest.append("Edge trend degrading")
    if edge and (edge.details or {}).get("trend") == "improving":
        strongest.append("Edge trend improving")

    open_q = [
        "Which sessions have insufficient observation coverage?",
        "Do replay assumptions still match live latency?",
        "Which operator tags cluster with losses?",
    ]

    return ModuleResult(
        module="weekly_review",
        status="available",
        score=Decimal(str(len(top_obs))),
        recommendation="Weekly learning review assembled",
        reasons=(
            "Top observations, unexpected findings, strong/weak conditions",
            "Open research questions only — no live changes",
        ),
        details={
            "top_observations": top_obs[:10],
            "unexpected_findings": unexpected[:10],
            "most_successful_conditions": strongest,
            "weakest_conditions": weakest,
            "open_research_questions": open_q,
            "period": "weekly",
            "recommends_live_changes": False,
        },
    )


def monthly_research_review(
    inp: LlpInput, modules: dict[str, ModuleResult]
) -> ModuleResult:
    _ = inp
    edge = modules.get("edge_evolution")
    obs = modules.get("live_observation_collector")
    cmp_ = modules.get("replay_comparison")
    conf = modules.get("confidence_tracking")

    return ModuleResult(
        module="monthly_research_review",
        status="available",
        score=obs.score if obs else None,
        recommendation="Monthly research review assembled",
        reasons=(
            "Edge, risk discipline, capital preservation, execution, validation",
            "Summary only — never auto-promotes",
        ),
        details={
            "edge_evolution": (
                (edge.details or {}).get("trend") if edge else INSUFFICIENT
            ),
            "risk_discipline": (
                "Observed via risk_usage fields on trades — not modified"
            ),
            "capital_preservation": (
                "Tracked via results in observations — advisory only"
            ),
            "execution_quality": (
                (cmp_.details or {}).get("unexpected_behaviour")
                if cmp_
                else []
            ),
            "validation_status": (
                (conf.details or {}).get("calibration_quality")
                if conf and conf.status == "available"
                else INSUFFICIENT
            ),
            "period": "monthly",
            "auto_promote": False,
            "recommends_live_changes": False,
        },
    )


def learning_dashboard(modules: dict[str, ModuleResult]) -> ModuleResult:
    obs = modules.get("live_observation_collector")
    fb = modules.get("operator_feedback")
    journal = modules.get("market_behaviour_journal")
    conf = modules.get("confidence_tracking")
    edge = modules.get("edge_evolution")
    rec = modules.get("research_recommendations")

    obs_count = int((obs.details or {}).get("observation_count") or 0) if obs else 0
    available = sum(
        1
        for k, v in modules.items()
        if k
        not in ("learning_dashboard", "research_recommendations")
        and v.status == "available"
    )
    total = max(
        sum(
            1
            for k in modules
            if k
            not in ("learning_dashboard", "research_recommendations")
        ),
        1,
    )
    strength = (Decimal(available) / Decimal(total) * Decimal(100)).quantize(
        Decimal("0.01")
    )

    # Coverage: observation fields + journal types + feedback
    coverage_bits = 0
    coverage_max = 3
    if obs_count > 0:
        coverage_bits += 1
    if journal and journal.status == "available":
        coverage_bits += 1
    if fb and fb.status == "available":
        coverage_bits += 1
    coverage = (
        Decimal(coverage_bits) / Decimal(coverage_max) * Decimal(100)
    ).quantize(Decimal("0.01"))

    queue = []
    if rec and isinstance((rec.details or {}).get("recommendations"), list):
        queue = (rec.details or {})["recommendations"][:8]

    progress = "nascent"
    if obs_count >= 100 and strength >= Decimal("70"):
        progress = "maturing"
    elif obs_count >= 30:
        progress = "building"

    return ModuleResult(
        module="learning_dashboard",
        status="available",
        score=strength,
        recommendation=f"Learning progress: {progress}",
        reasons=(
            "Progress, observation count, evidence strength, coverage, queue",
            "Dashboard is read-only",
        ),
        details={
            "learning_progress": progress,
            "observation_count": obs_count,
            "evidence_strength_pct": str(strength),
            "coverage_pct": str(coverage),
            "research_queue": queue,
            "edge_trend": (
                (edge.details or {}).get("trend") if edge else None
            ),
            "calibration_quality": (
                (conf.details or {}).get("calibration_quality")
                if conf
                else None
            ),
        },
    )


def research_recommendations(
    inp: LlpInput, modules: dict[str, ModuleResult], config: LlpConfig
) -> ModuleResult:
    _ = inp
    obs = modules.get("live_observation_collector")
    cmp_ = modules.get("replay_comparison")
    journal = modules.get("market_behaviour_journal")
    conf = modules.get("confidence_tracking")
    edge = modules.get("edge_evolution")

    recs: list[str] = []
    obs_count = int((obs.details or {}).get("observation_count") or 0) if obs else 0

    # Session coverage from observations
    sessions: dict[str, int] = defaultdict(int)
    if obs and isinstance((obs.details or {}).get("observations"), list):
        for o in (obs.details or {})["observations"]:
            s = o.get("session")
            if s:
                sessions[str(s).lower()] += 1
    for need in ("london", "new_york", "asia", "tokyo"):
        if sessions.get(need, 0) < 30:
            label = need.replace("_", " ").title()
            recs.append(f"Collect more {label}-session samples.")

    if journal and journal.status == "available":
        by_type = (journal.details or {}).get("by_type") or {}
        if int(by_type.get("news_days") or 0) < 20:
            recs.append("Replay News Regime with ≥250 trades.")
    else:
        recs.append("Populate market behaviour journal with day-type labels.")

    if obs_count < config.min_evidence_for_live_change_rec:
        recs.append(
            "Need more evidence before changing spread policy."
        )
        recs.append(
            "Do not recommend live parameter changes — "
            f"need ≥{config.min_evidence_for_live_change_rec} observations."
        )

    if conf and conf.status == "insufficient_evidence":
        recs.append("Collect predicted confidence vs outcome pairs for calibration.")
    if edge and edge.status == "insufficient_evidence":
        recs.append("Supply edge_score_series (daily/weekly/monthly/quarterly).")
    if cmp_ and (cmp_.details or {}).get("unexpected_behaviour"):
        recs.append(
            "Investigate replay vs live divergences before any policy change."
        )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)

    return ModuleResult(
        module="research_recommendations",
        status="available",
        score=Decimal(str(len(unique))),
        recommendation="Research recommendations only — no live changes",
        reasons=(
            "Recommendations are research backlog items",
            "Never recommend live changes without sufficient evidence",
        ),
        details={
            "recommendations": unique,
            "recommends_live_changes": False,
            "auto_tune": False,
            "auto_promote": False,
            "observation_count": obs_count,
            "min_for_live_change_rec": config.min_evidence_for_live_change_rec,
        },
    )
