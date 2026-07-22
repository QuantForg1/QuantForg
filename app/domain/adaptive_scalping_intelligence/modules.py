"""ASI intelligence modules — advisory, never fabricate statistics."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.adaptive_scalping_intelligence.config import AsiConfig
from app.domain.adaptive_scalping_intelligence.types import AsiInput, ModuleResult


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _hist(inp: AsiInput) -> list[dict[str, Any]]:
    rows = inp.historical_observations
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _insufficient(module: str, need: int, have: int) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="insufficient_history",
        source="none" if have == 0 else "historical",
        score=None,
        recommendation="Insufficient historical data",
        reasons=(
            f"Need ≥{need} observations; have {have}",
            "Never fabricates statistics when history is thin",
        ),
        details={"required": need, "available": have},
    )


def detect_market_personality(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    hist = _hist(inp)
    live_bits: list[str] = []
    if inp.regime:
        live_bits.append(f"live regime={inp.regime}")
    if inp.volatility:
        live_bits.append(f"live volatility={inp.volatility}")
    if inp.personality_hint:
        live_bits.append(f"live hint={inp.personality_hint}")

    if len(hist) < config.min_history_observations:
        if live_bits:
            return ModuleResult(
                module="market_personality",
                status="empty",
                source="live",
                score=None,
                recommendation="Live only — history insufficient",
                reasons=(
                    *live_bits,
                    f"Historical samples {len(hist)} "
                    f"< {config.min_history_observations}",
                    "Personality not inferred from thin history",
                ),
                details={
                    "live": {
                        "regime": inp.regime,
                        "volatility": inp.volatility,
                        "hint": inp.personality_hint,
                    },
                    "historical_personality": None,
                },
            )
        return _insufficient(
            "market_personality", config.min_history_observations, len(hist)
        )

    labels = [
        str(r.get("personality") or r.get("regime") or "unknown") for r in hist
    ]
    counts = Counter(labels)
    top, top_n = counts.most_common(1)[0]
    share = (Decimal(top_n) / Decimal(len(hist)) * Decimal(100)).quantize(
        Decimal("0.01")
    )
    return ModuleResult(
        module="market_personality",
        status="available",
        source="mixed" if live_bits else "historical",
        score=share,
        recommendation=f"Dominant personality: {top}",
        reasons=(
            *live_bits,
            f"Historical dominant={top} ({share}% of {len(hist)} obs)",
            "Live and historical are reported separately",
        ),
        details={
            "live": {
                "regime": inp.regime,
                "volatility": inp.volatility,
                "hint": inp.personality_hint,
            },
            "historical_personality": top,
            "historical_distribution": dict(counts),
            "sample_size": len(hist),
        },
    )


def evaluate_session_intelligence(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    hist = _hist(inp)
    session = (inp.session or "").lower() or None
    if not session and not hist:
        return ModuleResult(
            module="session_intelligence",
            status="empty",
            source="none",
            score=None,
            recommendation="Await session facts",
            reasons=("No live session and no historical rows",),
        )

    by_session: dict[str, list[Decimal]] = defaultdict(list)
    for r in hist:
        s = str(r.get("session") or "").lower()
        q = _dec(r.get("quality") or r.get("outcome_score"))
        if s and q is not None:
            by_session[s].append(q)

    if session and session not in by_session and len(hist) < config.min_session_samples:
        return ModuleResult(
            module="session_intelligence",
            status="insufficient_history",
            source="live",
            score=None,
            recommendation="Insufficient session history",
            reasons=(
                f"Live session={session}",
                f"Need ≥{config.min_session_samples} samples for this session",
            ),
            details={"live_session": session, "historical_avg": None},
        )

    hist_avg = None
    sample_n = 0
    if session and by_session.get(session):
        vals = by_session[session]
        sample_n = len(vals)
        hist_avg = (sum(vals) / Decimal(len(vals))).quantize(Decimal("0.01"))
    elif not session and by_session:
        # overall best session from history only
        best_s, best_vals = max(
            by_session.items(), key=lambda kv: sum(kv[1]) / len(kv[1])
        )
        sample_n = len(best_vals)
        hist_avg = (sum(best_vals) / Decimal(len(best_vals))).quantize(
            Decimal("0.01")
        )
        session = best_s

    if hist_avg is None:
        return _insufficient(
            "session_intelligence", config.min_session_samples, sample_n
        )
    if sample_n < config.min_session_samples:
        return _insufficient(
            "session_intelligence", config.min_session_samples, sample_n
        )

    return ModuleResult(
        module="session_intelligence",
        status="available",
        source="mixed" if inp.session else "historical",
        score=hist_avg,
        recommendation=f"Session {session} historical quality {hist_avg}",
        reasons=(
            f"Live session={inp.session or 'n/a'}",
            f"Historical avg quality for {session}={hist_avg} (n={sample_n})",
            "Does not change session filters automatically",
        ),
        details={
            "live_session": inp.session,
            "historical_session": session,
            "historical_avg_quality": str(hist_avg),
            "sample_size": sample_n,
            "sessions_seen": {k: len(v) for k, v in by_session.items()},
        },
    )


def evaluate_time_intelligence(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    hist = _hist(inp)
    if len(hist) < config.min_history_observations:
        live = []
        if inp.hour_utc is not None:
            live.append(f"live hour_utc={inp.hour_utc}")
        if inp.weekday:
            live.append(f"live weekday={inp.weekday}")
        if live:
            return ModuleResult(
                module="time_intelligence",
                status="insufficient_history",
                source="live",
                score=None,
                recommendation="Live clock only — history thin",
                reasons=(*live, "No historical time edge computed"),
                details={
                    "live_hour_utc": inp.hour_utc,
                    "live_weekday": inp.weekday,
                },
            )
        return _insufficient(
            "time_intelligence", config.min_history_observations, len(hist)
        )

    hour_scores: dict[int, list[Decimal]] = defaultdict(list)
    for r in hist:
        h = r.get("hour_utc")
        q = _dec(r.get("quality") or r.get("outcome_score"))
        if h is None or q is None:
            continue
        try:
            hour_scores[int(h)].append(q)
        except (TypeError, ValueError):
            continue
    if not hour_scores:
        return ModuleResult(
            module="time_intelligence",
            status="empty",
            source="historical",
            score=None,
            recommendation="History lacks hour_utc/quality fields",
            reasons=("Cannot compute time edge without hour tags",),
        )

    ranked = sorted(
        (
            (h, (sum(vs) / Decimal(len(vs))).quantize(Decimal("0.01")), len(vs))
            for h, vs in hour_scores.items()
        ),
        key=lambda t: t[1],
        reverse=True,
    )
    best_h, best_avg, best_n = ranked[0]
    live_note = (
        f"live hour_utc={inp.hour_utc}"
        if inp.hour_utc is not None
        else "no live hour"
    )
    return ModuleResult(
        module="time_intelligence",
        status="available",
        source="mixed" if inp.hour_utc is not None else "historical",
        score=best_avg,
        recommendation=f"Historically stronger hour UTC {best_h}",
        reasons=(
            live_note,
            f"Best historical hour={best_h} avg={best_avg} (n={best_n})",
            "Advisory only — does not change trading hours automatically",
        ),
        details={
            "live_hour_utc": inp.hour_utc,
            "live_weekday": inp.weekday,
            "top_hours": [
                {"hour_utc": h, "avg": str(a), "n": n} for h, a, n in ranked[:5]
            ],
        },
    )


def build_opportunity_database(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    catalog = (
        inp.opportunity_catalog
        if isinstance(inp.opportunity_catalog, list)
        else []
    )
    catalog = [c for c in catalog if isinstance(c, dict)]
    hist = _hist(inp)
    # Merge catalog + historical opportunity ids (observation store)
    rows: list[dict[str, Any]] = list(catalog)
    for r in hist:
        if r.get("opportunity_id") or r.get("pattern_id"):
            rows.append(r)
    if not rows:
        live = inp.live_opportunity if isinstance(inp.live_opportunity, dict) else None
        if live:
            return ModuleResult(
                module="scalping_opportunity_database",
                status="empty",
                source="live",
                score=None,
                recommendation="Live opportunity only — DB empty",
                reasons=(
                    "No historical opportunity catalog supplied",
                    "Live observation recorded separately",
                ),
                details={"live": live, "database_size": 0},
            )
        return ModuleResult(
            module="scalping_opportunity_database",
            status="empty",
            source="none",
            score=None,
            recommendation="Opportunity database empty",
            reasons=("No catalog or historical opportunity rows",),
            details={"database_size": 0},
        )

    capped = rows[: config.max_opportunity_db]
    ids = [
        str(r.get("opportunity_id") or r.get("pattern_id") or r.get("id") or "")
        for r in capped
    ]
    ids = [i for i in ids if i]
    return ModuleResult(
        module="scalping_opportunity_database",
        status="available",
        source="historical" if not inp.live_opportunity else "mixed",
        score=Decimal(len(capped)),
        recommendation=f"{len(capped)} stored opportunity observations",
        reasons=(
            f"Database size {len(capped)} (cap {config.max_opportunity_db})",
            "Never invents missing opportunity rows",
            "Does not auto-promote setups into live rules",
        ),
        details={
            "database_size": len(capped),
            "unique_ids": len(set(ids)),
            "live": inp.live_opportunity,
            "sample_ids": ids[:10],
        },
    )


def evaluate_pattern_intelligence(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    hist = _hist(inp)
    pattern = inp.pattern_id
    matches = [
        r
        for r in hist
        if str(r.get("pattern_id") or r.get("opportunity_id") or "") == str(pattern)
    ] if pattern else []
    if pattern and len(matches) < config.min_pattern_samples:
        return ModuleResult(
            module="pattern_intelligence",
            status="insufficient_history",
            source="live" if pattern else "none",
            score=None,
            recommendation="Insufficient pattern history",
            reasons=(
                f"Live pattern={pattern}",
                f"Matches {len(matches)} < {config.min_pattern_samples}",
            ),
            details={"live_pattern": pattern, "matches": len(matches)},
        )
    if not pattern:
        # Rank patterns by frequency when no live pattern
        counter = Counter(
            str(r.get("pattern_id") or r.get("opportunity_id") or "unknown")
            for r in hist
            if r.get("pattern_id") or r.get("opportunity_id")
        )
        if sum(counter.values()) < config.min_pattern_samples:
            return _insufficient(
                "pattern_intelligence",
                config.min_pattern_samples,
                sum(counter.values()),
            )
        top = counter.most_common(5)
        return ModuleResult(
            module="pattern_intelligence",
            status="available",
            source="historical",
            score=Decimal(top[0][1]) if top else None,
            recommendation="Historical pattern frequency ranking",
            reasons=(
                "No live pattern_id — showing historical frequencies only",
                "Advisory — does not rewrite pattern filters",
            ),
            details={"top_patterns": [{"id": i, "n": n} for i, n in top]},
        )

    wins = sum(1 for r in matches if r.get("win") is True)
    n = len(matches)
    wr = (Decimal(wins) / Decimal(n) * Decimal(100)).quantize(Decimal("0.01"))
    return ModuleResult(
        module="pattern_intelligence",
        status="available",
        source="mixed",
        score=wr,
        recommendation=f"Pattern {pattern} historical win rate {wr}%",
        reasons=(
            f"Live pattern={pattern}",
            f"Historical n={n}, wins={wins}, win_rate={wr}%",
            "Not a profitability guarantee",
        ),
        details={
            "live_pattern": pattern,
            "sample_size": n,
            "wins": wins,
            "historical_win_rate_pct": str(wr),
        },
    )


def calibrate_confidence(inp: AsiInput, config: AsiConfig) -> ModuleResult:
    hist = _hist(inp)
    closed = inp.closed_trades if isinstance(inp.closed_trades, list) else []
    closed = [c for c in closed if isinstance(c, dict)]
    samples = hist if hist else closed
    if len(samples) < config.min_calibration_samples:
        live = inp.live_confidence
        return ModuleResult(
            module="confidence_calibration",
            status="insufficient_history",
            source="live" if live is not None else "none",
            score=None,
            recommendation="Insufficient data to calibrate",
            reasons=(
                f"Live confidence={live}" if live is not None else "No live confidence",
                f"Samples {len(samples)} < {config.min_calibration_samples}",
                "Never invents a calibration curve",
            ),
            details={
                "live_confidence": str(live) if live is not None else None,
                "sample_size": len(samples),
            },
        )

    # Bucket predicted confidence vs realized win
    buckets: dict[str, list[bool]] = defaultdict(list)
    for r in samples:
        conf = _dec(r.get("confidence") or r.get("predicted_confidence"))
        win = r.get("win")
        if conf is None or not isinstance(win, bool):
            continue
        if conf < 50:
            key = "lt50"
        elif conf < 70:
            key = "50_70"
        else:
            key = "gte70"
        buckets[key].append(win)

    if not buckets:
        return ModuleResult(
            module="confidence_calibration",
            status="empty",
            source="historical",
            score=None,
            recommendation="History lacks confidence/win pairs",
            reasons=("Cannot calibrate without paired outcomes",),
        )

    curve = {}
    for key, wins in buckets.items():
        wr = (
            Decimal(sum(1 for w in wins if w))
            / Decimal(len(wins))
            * Decimal(100)
        ).quantize(Decimal("0.01"))
        curve[key] = {"n": len(wins), "realized_win_rate_pct": str(wr)}

    live = inp.live_confidence
    advice = "Report calibration only — does not auto-adjust confidence gates"
    return ModuleResult(
        module="confidence_calibration",
        status="available",
        source="mixed" if live is not None else "historical",
        score=_dec(curve.get("gte70", {}).get("realized_win_rate_pct")),
        recommendation="Confidence calibration curve available",
        reasons=(
            f"Live confidence={live}" if live is not None else "No live confidence",
            advice,
            "Not a promise of future win rate",
        ),
        details={
            "live_confidence": str(live) if live is not None else None,
            "calibration_curve": curve,
            "sample_size": len(samples),
            "auto_modifies_thresholds": False,
        },
    )


def build_opportunity_heat_map(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    hist = _hist(inp)
    if len(hist) < config.min_history_observations:
        return _insufficient(
            "opportunity_heat_map",
            config.min_history_observations,
            len(hist),
        )

    grid: dict[str, dict[str, list[Decimal]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in hist:
        session = str(r.get("session") or "unknown")
        hour = r.get("hour_utc")
        q = _dec(r.get("quality") or r.get("outcome_score"))
        if hour is None or q is None:
            continue
        try:
            bucket = int(hour) // max(1, 24 // max(1, config.heat_map_buckets))
        except (TypeError, ValueError):
            continue
        grid[session][str(bucket)].append(q)

    if not grid:
        return ModuleResult(
            module="opportunity_heat_map",
            status="empty",
            source="historical",
            score=None,
            recommendation="Cannot build heat map — missing session/hour/quality",
            reasons=("Historical rows lack required fields",),
        )

    cells = []
    for session, buckets in grid.items():
        for b, vals in buckets.items():
            avg = (sum(vals) / Decimal(len(vals))).quantize(Decimal("0.01"))
            cells.append(
                {
                    "session": session,
                    "time_bucket": b,
                    "avg_quality": str(avg),
                    "n": len(vals),
                    "source": "historical",
                }
            )
    cells.sort(key=lambda c: Decimal(c["avg_quality"]), reverse=True)
    top = cells[0]
    return ModuleResult(
        module="opportunity_heat_map",
        status="available",
        source="historical",
        score=Decimal(top["avg_quality"]),
        recommendation=(
            f"Hottest historical cell: {top['session']} bucket {top['time_bucket']}"
        ),
        reasons=(
            f"{len(cells)} historical heat cells",
            "Live opportunity not painted into map unless supplied separately",
            "Advisory visualization only",
        ),
        details={
            "cells": cells[:40],
            "live_session": inp.session,
            "live_hour_utc": inp.hour_utc,
            "cell_count": len(cells),
        },
    )


def capital_preservation_index(
    inp: AsiInput, config: AsiConfig
) -> ModuleResult:
    _ = config
    facts = inp.capital_facts if isinstance(inp.capital_facts, dict) else {}
    closed = inp.closed_trades if isinstance(inp.closed_trades, list) else []
    closed = [c for c in closed if isinstance(c, dict)]

    if not facts and not closed:
        return ModuleResult(
            module="capital_preservation_index",
            status="empty",
            source="none",
            score=None,
            recommendation="Await capital facts",
            reasons=("No capital_facts or closed_trades supplied",),
        )

    reasons: list[str] = []
    score = Decimal("70")
    source = "live"
    if facts:
        dd = _dec(facts.get("max_drawdown_pct") or facts.get("drawdown_pct"))
        daily = _dec(facts.get("daily_loss_pct"))
        if dd is not None:
            reasons.append(f"Live/max drawdown {dd}%")
            score -= min(dd * Decimal("5"), Decimal("40"))
        if daily is not None:
            reasons.append(f"Daily loss {daily}%")
            score -= min(daily * Decimal("8"), Decimal("30"))
    if closed:
        source = "mixed" if facts else "historical"
        losses = 0
        for c in closed:
            pnl = _dec(c.get("pnl"))
            if c.get("win") is False or (pnl is not None and pnl < 0):
                losses += 1
        reasons.append(
            f"Historical closed trades n={len(closed)}, losses={losses}"
        )
        if len(closed) >= 5:
            loss_rate = Decimal(losses) / Decimal(len(closed))
            score -= loss_rate * Decimal("20")

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(Decimal("0.01"))
    reasons.append("Index is observational — not a profit guarantee")
    reasons.append("Never auto-modifies risk policies")
    return ModuleResult(
        module="capital_preservation_index",
        status="available",
        source=source,
        score=score,
        recommendation=f"Capital preservation index {score}",
        reasons=tuple(reasons),
        details={
            "live_facts": facts or None,
            "closed_trade_count": len(closed),
            "auto_modifies_risk_policies": False,
        },
    )


def explain_decision(inp: AsiInput, modules: dict[str, ModuleResult]) -> ModuleResult:
    ctx = inp.decision_context if isinstance(inp.decision_context, dict) else {}
    bullets: list[str] = []
    if ctx:
        dec = ctx.get("decision") or ctx.get("recommendation") or "n/a"
        bullets.append(f"Decision context decision={dec}")
        for k in ("reason", "rationale", "summary"):
            if ctx.get(k):
                bullets.append(f"Context {k}: {ctx[k]}")
    for name, mod in modules.items():
        if mod.status == "insufficient_history":
            bullets.append(f"{name}: insufficient history")
        elif mod.status == "available":
            bullets.append(f"{name}: {mod.recommendation}")
    if not bullets:
        bullets.append("No decision context or module outputs to explain")
    return ModuleResult(
        module="decision_explainability",
        status="available" if bullets else "empty",
        source="mixed" if ctx else "historical",
        score=None,
        recommendation="Explainable advisory summary",
        reasons=tuple(bullets[:20]),
        details={
            "decision_context": ctx or None,
            "module_count": len(modules),
            "auditable": True,
            "auto_modifies_rules": False,
        },
    )


def weekly_ai_coach_report(inp: AsiInput, config: AsiConfig) -> ModuleResult:
    hist = _hist(inp)
    closed = inp.closed_trades if isinstance(inp.closed_trades, list) else []
    closed = [c for c in closed if isinstance(c, dict)]
    pool = closed if closed else hist
    if len(pool) < config.min_calibration_samples:
        return ModuleResult(
            module="weekly_ai_coach",
            status="insufficient_history",
            source="none" if not pool else "historical",
            score=None,
            recommendation="Insufficient data for weekly coach",
            reasons=(
                (
                    f"Need ≥{config.min_calibration_samples} observations; "
                    f"have {len(pool)}"
                ),
                f"Lookback target {config.coach_lookback_days}d "
                "(caller-filtered)",
                "Coach never auto-modifies trading rules",
            ),
            details={
                "lookback_days": config.coach_lookback_days,
                "sample_size": len(pool),
                "lessons": [],
            },
        )

    wins = sum(1 for r in pool if r.get("win") is True)
    n = len(pool)
    wr = (Decimal(wins) / Decimal(n) * Decimal(100)).quantize(Decimal("0.01"))
    lessons = [
        f"Observed win rate {wr}% over {n} supplied rows (historical)",
        "Prefer No Trade when session/time heat is cold (see heat map)",
        "Do not change risk policies from this report automatically",
        "Treat live observations separately from historical metrics",
    ]
    if inp.session:
        lessons.insert(0, f"Live session in focus: {inp.session}")
    return ModuleResult(
        module="weekly_ai_coach",
        status="available",
        source="historical",
        score=wr,
        recommendation="Weekly coach report (advisory)",
        reasons=tuple(lessons),
        details={
            "lookback_days": config.coach_lookback_days,
            "sample_size": n,
            "historical_win_rate_pct": str(wr),
            "lessons": lessons,
            "auto_modifies_trading_rules": False,
            "auto_modifies_risk_policies": False,
            "promise_profitability": False,
        },
    )
