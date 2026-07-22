"""Institutional Performance Intelligence — journal/evidence aggregation only.

Never modifies strategy, risk, safety, or execution. Never fabricates metrics.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.execution_intelligence.trend_analytics import (
    _bucket_stats,
    _parse_ts,
    _pnl,
    _r_multiple,
    compute_regime_analytics,
    compute_risk_trends,
)
from app.domain.institutional_trading.xauusd_strategy_audit import audit_no_trade

SIGNAL_KEYS = (
    "bos",
    "choch",
    "liquidity_sweep",
    "order_block",
    "fair_value_gap",
    "confluence",
)


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def normalize_trade_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Map journal / deal / research rows into a common trade-like shape."""
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        pnl = raw.get("net_pnl")
        if pnl is None:
            pnl = raw.get("pnl")
        if pnl is None:
            pnl = raw.get("profit")
        if pnl is None:
            pnl = raw.get("netPl")
        # Skip rows with no PnL evidence — never invent
        if pnl is None:
            continue
        out.append(
            {
                "net_pnl": _f(pnl),
                "pnl": _f(pnl),
                "opened_at": raw.get("opened_at")
                or raw.get("entry_at")
                or raw.get("created_at")
                or raw.get("submitted_at"),
                "closed_at": raw.get("closed_at")
                or raw.get("exit_at")
                or raw.get("completed_at")
                or raw.get("filled_at"),
                "session": raw.get("session")
                or raw.get("market_session")
                or raw.get("trading_session"),
                "regime": raw.get("regime") or raw.get("market_regime"),
                "r_multiple": raw.get("r_multiple")
                or raw.get("rr")
                or raw.get("reward_risk"),
                "risk_amount": raw.get("risk_amount") or raw.get("initial_risk"),
                "exit_cause": raw.get("exit_cause")
                or raw.get("exit_reason")
                or raw.get("stop_reason"),
                "hold_sec": raw.get("hold_sec")
                or raw.get("holding_time_sec")
                or raw.get("duration_seconds"),
                "signals": raw.get("signals") or raw.get("signal_tags") or [],
                "confluence": raw.get("confluence")
                if isinstance(raw.get("confluence"), dict)
                else {},
                "confluence_score": raw.get("confluence_score")
                or raw.get("confidence"),
                "bos": raw.get("bos"),
                "choch": raw.get("choch"),
                "liquidity_sweep": raw.get("liquidity_sweep")
                or raw.get("sweep"),
                "order_block": raw.get("order_block"),
                "fair_value_gap": raw.get("fair_value_gap") or raw.get("fvg"),
                "time_to_tp_sec": raw.get("time_to_tp_sec"),
                "time_to_sl_sec": raw.get("time_to_sl_sec"),
            }
        )
    return out


def normalize_decision_rows(
    rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        out.append(
            {
                "decision": raw.get("decision")
                or raw.get("action")
                or raw.get("decision_action"),
                "reason": raw.get("reason")
                or raw.get("why")
                or raw.get("rejected")
                or raw.get("abort_reason"),
                "confluence": raw.get("confluence")
                if isinstance(raw.get("confluence"), dict)
                else {},
                "timestamp": raw.get("timestamp")
                or raw.get("created_at")
                or raw.get("submitted_at"),
            }
        )
    return out


def compute_performance_dashboard(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Core institutional KPIs from supplied closed trades only."""
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No closed trades with PnL supplied",
            "metrics": {},
        }

    wins = [t for t in trades if _pnl(t) > 0]
    losses = [t for t in trades if _pnl(t) < 0]
    pnls = [_pnl(t) for t in trades]
    gross_win = sum(pnls[i] for i, t in enumerate(trades) if _pnl(t) > 0)
    gross_loss = abs(sum(pnls[i] for i, t in enumerate(trades) if _pnl(t) < 0))
    n = len(trades)
    win_rate = len(wins) / n if n else None
    avg_win = (gross_win / len(wins)) if wins else None
    avg_loss = (gross_loss / len(losses)) if losses else None
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    pf = (gross_win / gross_loss) if gross_loss > 0 else None

    rs = [r for r in (_r_multiple(t) for t in trades) if r is not None]
    risk = compute_risk_trends(trades)
    trends = dict(risk.get("trends") or {})
    max_dd = trends.get("monthly_drawdown_pct")
    if max_dd is None:
        max_dd = trends.get("weekly_drawdown_pct")
    net = sum(pnls)
    recovery = None
    if max_dd is not None and float(max_dd) > 0 and abs(net) > 0:
        # Recovery factor ≈ net profit / max drawdown (absolute units when DD is %)
        # Use equity peak approximation: DD% of peak; without peak use |DD| as proxy.
        recovery = round(net / float(max_dd), 4) if float(max_dd) else None

    return {
        "status": "available",
        "metrics": {
            "total_trades": n,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
            "profit_factor": round(pf, 4) if pf is not None else None,
            "expectancy": round(expectancy, 6) if expectancy is not None else None,
            "average_win": round(avg_win, 4) if avg_win is not None else None,
            "average_loss": round(avg_loss, 4) if avg_loss is not None else None,
            "average_rr": round(sum(rs) / len(rs), 4) if rs else None,
            "largest_win": round(max(pnls), 4) if pnls else None,
            "largest_loss": round(min(pnls), 4) if pnls else None,
            "consecutive_wins": trends.get("consecutive_wins_max"),
            "consecutive_losses": trends.get("consecutive_losses_max"),
            "maximum_drawdown_pct": max_dd,
            "recovery_factor": recovery,
            "net_pnl": round(net, 4),
        },
        "sample_size": n,
        "note": "From supplied closed-trade PnL only — never fabricated",
    }


def enrich_session_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-session stats with net P/L and average RR — sessions never mixed."""
    from app.domain.institutional_trading.session_filter import classify_session_utc

    buckets: dict[str, list[dict[str, Any]]] = {
        "sydney": [],
        "tokyo": [],
        "london": [],
        "new_york": [],
        "overlap": [],
        "off_hours": [],
    }
    for t in trades:
        label = str(t.get("session") or t.get("market_session") or "").lower()
        aliases = {
            "london_ny_overlap": "overlap",
            "london_new_york_overlap": "overlap",
            "ny": "new_york",
        }
        label = aliases.get(label, label)
        if label not in buckets:
            ts = _parse_ts(
                t.get("opened_at") or t.get("closed_at") or t.get("created_at")
            )
            if ts:
                raw = classify_session_utc(ts).value
                label = (
                    "overlap" if raw == "london_ny_overlap" else raw
                )
            else:
                label = "off_hours"
        if label not in buckets:
            label = "off_hours"
        buckets[label].append(t)

    def _enrich(rows: list[dict[str, Any]]) -> dict[str, Any]:
        stats = _bucket_stats(rows)
        rs = [r for r in (_r_multiple(t) for t in rows) if r is not None]
        return {
            **stats,
            "average_rr": round(sum(rs) / len(rs), 4) if rs else None,
            "net_pnl": round(sum(_pnl(t) for t in rows), 4) if rows else None,
        }

    sessions = {k: _enrich(v) for k, v in buckets.items()}
    return {
        "status": "available" if trades else "unavailable",
        "overall": _enrich(trades),
        "sessions": sessions,
        "note": "Sessions evaluated separately — never mixed",
    }


def enrich_regime_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    base = compute_regime_analytics(trades)
    regimes = dict(base.get("regimes") or {})
    out: dict[str, Any] = {}
    for key, stats in regimes.items():
        bucket = [
            t
            for t in trades
            if str(t.get("regime") or t.get("market_regime") or "")
            .lower()
            .strip()
            in {
                key,
                key.replace("_", " "),
                "trending" if key == "trend" else key,
                "ranging" if key == "range" else key,
                "hv" if key == "high_volatility" else key,
                "lv" if key == "low_volatility" else key,
            }
        ]
        hold = stats.get("avg_duration_seconds")
        if bucket and hold is None:
            hold = _bucket_stats(bucket).get("avg_duration_seconds")
        out[key] = {
            "trade_count": stats.get("trade_count"),
            "win_rate": stats.get("win_rate"),
            "expectancy": stats.get("expectancy"),
            "average_hold_seconds": hold,
            "status": stats.get("status"),
        }
    # Ensure required regime keys
    for req in ("trend", "range", "high_volatility", "low_volatility"):
        out.setdefault(
            req,
            {
                "trade_count": 0,
                "win_rate": None,
                "expectancy": None,
                "average_hold_seconds": None,
                "status": "empty",
            },
        )
    return {
        "status": base.get("status"),
        "regimes": out,
        "unlabeled_trades": base.get("unlabeled_trades", 0),
        "note": "Regimes evaluated separately — never mixed; unlabeled excluded",
    }


def _signal_flags(t: dict[str, Any]) -> set[str]:
    flags: set[str] = set()
    tags = t.get("signals")
    if isinstance(tags, list):
        for tag in tags:
            s = str(tag).lower().strip()
            if s in SIGNAL_KEYS or s in {"sweep", "fvg", "ob"}:
                aliases = {
                    "sweep": "liquidity_sweep",
                    "fvg": "fair_value_gap",
                    "ob": "order_block",
                }
                flags.add(aliases.get(s, s))
    for key in ("bos", "choch", "liquidity_sweep", "order_block", "fair_value_gap"):
        if t.get(key) is True:
            flags.add(key)
    conf = t.get("confluence") if isinstance(t.get("confluence"), dict) else {}
    factors = conf.get("factors") if isinstance(conf.get("factors"), dict) else {}
    reasons = conf.get("reasons") if isinstance(conf.get("reasons"), list) else []
    reason_text = " ".join(str(r) for r in reasons).lower()
    if "bos" in reason_text:
        flags.add("bos")
    if "choch" in reason_text or "change of character" in reason_text:
        flags.add("choch")
    if "sweep" in reason_text:
        flags.add("liquidity_sweep")
    if "order block" in reason_text or factors.get("order_block"):
        flags.add("order_block")
    if "fvg" in reason_text or "fair value" in reason_text or factors.get("fvg"):
        flags.add("fair_value_gap")
    score = t.get("confluence_score")
    if score is None:
        score = conf.get("score") or conf.get("confidence")
    if score is not None:
        flags.add("confluence")
    return flags


def compute_signal_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Performance by SMC signal tags — combinations when tagged."""
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No closed trades supplied",
            "signals": {},
            "combinations": [],
        }

    by_signal: dict[str, list[dict[str, Any]]] = {k: [] for k in SIGNAL_KEYS}
    combos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tagged = 0
    for t in trades:
        flags = _signal_flags(t)
        if not flags:
            continue
        tagged += 1
        for f in flags:
            if f in by_signal:
                by_signal[f].append(t)
        combo_key = "+".join(sorted(flags - {"confluence"})) or "confluence_only"
        combos[combo_key].append(t)

    signals = {k: _bucket_stats(v) for k, v in by_signal.items()}
    # Confluence score bands when numeric score present
    bands: dict[str, list[dict[str, Any]]] = {
        "confluence_90_plus": [],
        "confluence_80_89": [],
        "confluence_below_80": [],
    }
    for t in trades:
        conf = t.get("confluence") if isinstance(t.get("confluence"), dict) else {}
        score = t.get("confluence_score")
        if score is None:
            score = conf.get("score") or conf.get("confidence")
        if score is None:
            continue
        s = _f(score)
        if s >= 90:
            bands["confluence_90_plus"].append(t)
        elif s >= 80:
            bands["confluence_80_89"].append(t)
        else:
            bands["confluence_below_80"].append(t)
    for k, v in bands.items():
        signals[k] = _bucket_stats(v)

    ranked = sorted(
        (
            {
                "combination": key,
                **_bucket_stats(rows),
            }
            for key, rows in combos.items()
            if rows
        ),
        key=lambda r: (
            r.get("expectancy") is not None,
            r.get("expectancy") or -1e18,
            r.get("trade_count") or 0,
        ),
        reverse=True,
    )
    return {
        "status": "available" if tagged else "insufficient_tags",
        "tagged_trades": tagged,
        "untagged_trades": max(0, len(trades) - tagged),
        "signals": signals,
        "combinations": ranked[:20],
        "best_combination": ranked[0] if ranked else None,
        "note": "Signal tags from supplied confluence/reasons only — never invented",
    }


def compute_no_trade_analytics(
    decisions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    base = audit_no_trade(decisions)
    if base.get("status") != "available":
        return {
            **base,
            "reason_histogram": {},
            "estimated_bad_trades_avoided": None,
            "research_only": True,
        }

    hist: dict[str, int] = defaultdict(int)
    for d in decisions or []:
        action = (
            str(d.get("decision") or d.get("action") or "")
            .upper()
            .replace(" ", "_")
        )
        if action not in {"NO_TRADE", "REJECT", "WATCH", "BLOCKED"}:
            continue
        reason = str(
            d.get("reason") or d.get("why") or d.get("rejected") or "unspecified"
        )
        hist[reason[:120]] += 1

    # Research-only estimate: count NO_TRADE with risk/spread/news reasons —
    # never claim as realized PnL saved.
    riskish = sum(
        c
        for r, c in hist.items()
        if any(
            k in r.lower()
            for k in ("spread", "news", "mtf", "quality", "session", "volatility")
        )
    )
    return {
        **base,
        "reason_histogram": dict(sorted(hist.items(), key=lambda x: -x[1])[:30]),
        "estimated_bad_trades_avoided": {
            "count_proxy": riskish,
            "status": "research_only",
            "note": (
                "Proxy count of NO_TRADE decisions with risk/quality reasons — "
                "not realized PnL; never fabricates savings"
            ),
        },
        "research_only": True,
    }


def compute_time_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No closed trades supplied",
            "metrics": {},
        }
    durations: list[float] = []
    to_tp: list[float] = []
    to_sl: list[float] = []
    for t in trades:
        hold = t.get("hold_sec")
        if hold is not None:
            durations.append(_f(hold))
        else:
            start = _parse_ts(t.get("opened_at"))
            end = _parse_ts(t.get("closed_at"))
            if start and end and end >= start:
                durations.append((end - start).total_seconds())
        if t.get("time_to_tp_sec") is not None:
            to_tp.append(_f(t.get("time_to_tp_sec")))
        if t.get("time_to_sl_sec") is not None:
            to_sl.append(_f(t.get("time_to_sl_sec")))
        # Infer TP/SL from exit cause when duration known
        cause = str(t.get("exit_cause") or "").lower()
        if durations and "tp" in cause and t.get("time_to_tp_sec") is None:
            # use last computed duration for this trade
            start = _parse_ts(t.get("opened_at"))
            end = _parse_ts(t.get("closed_at"))
            if start and end:
                to_tp.append((end - start).total_seconds())
        if durations and ("sl" in cause or "stop" in cause) and t.get(
            "time_to_sl_sec"
        ) is None:
            start = _parse_ts(t.get("opened_at"))
            end = _parse_ts(t.get("closed_at"))
            if start and end:
                to_sl.append((end - start).total_seconds())

    return {
        "status": "available" if durations else "insufficient_timestamps",
        "metrics": {
            "average_trade_duration_seconds": (
                round(sum(durations) / len(durations), 2) if durations else None
            ),
            "fastest_trade_seconds": round(min(durations), 2) if durations else None,
            "longest_trade_seconds": round(max(durations), 2) if durations else None,
            "average_time_to_tp_seconds": (
                round(sum(to_tp) / len(to_tp), 2) if to_tp else None
            ),
            "average_time_to_sl_seconds": (
                round(sum(to_sl) / len(to_sl), 2) if to_sl else None
            ),
            "duration_sample_size": len(durations),
            "tp_sample_size": len(to_tp),
            "sl_sample_size": len(to_sl),
        },
        "note": "Missing timestamps stay null — never fabricated",
    }


def build_period_report(
    trades: list[dict[str, Any]],
    *,
    period: str,
    decisions: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Daily / weekly / monthly composite report from evidence."""
    period_l = period.lower().strip()
    if period_l not in {"daily", "weekly", "monthly"}:
        period_l = "daily"
    moment = now or datetime.now(UTC)
    delta = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30),
    }[period_l]
    cutoff = moment - delta

    window = []
    for t in trades:
        ts = _parse_ts(t.get("closed_at") or t.get("opened_at"))
        if ts is None or ts >= cutoff:
            window.append(t)

    perf = compute_performance_dashboard(window)
    sessions = enrich_session_analytics(window)
    regimes = enrich_regime_analytics(window)
    signals = compute_signal_analytics(window)
    risk = compute_risk_trends(window)
    no_trade = compute_no_trade_analytics(decisions)

    open_questions: list[str] = []
    if int(perf.get("sample_size") or 0) < 20:
        open_questions.append("Need more closed trades in this period for stable KPIs")
    if int(regimes.get("unlabeled_trades") or 0) > 0:
        open_questions.append(
            "Persist regime labels on closed deals for regime period reports"
        )
    if signals.get("status") == "insufficient_tags":
        open_questions.append(
            "Tag confluence factors on journal rows for signal analytics"
        )
    if no_trade.get("status") != "available":
        open_questions.append("Export Decision Engine NO_TRADE journal for refusal IQ")

    return {
        "period": period_l,
        "generated_at": moment.isoformat(),
        "window_start": cutoff.isoformat(),
        "performance_summary": perf,
        "risk_summary": risk,
        "session_summary": sessions,
        "strategy_summary": signals,
        "no_trade_summary": no_trade,
        "open_questions": open_questions,
        "never_auto_modifies_strategy": True,
    }


def build_recommendations(
    *,
    performance: dict[str, Any],
    sessions: dict[str, Any],
    regimes: dict[str, Any],
    signals: dict[str, Any],
    no_trade: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    metrics = performance.get("metrics") or {}
    n = int(metrics.get("total_trades") or 0)
    if n < 50:
        recs.append(f"Need more closed-trade evidence (have {n}, want >=50)")

    sess = sessions.get("sessions") or {}
    for name in ("london", "new_york", "overlap", "tokyo", "sydney"):
        c = int((sess.get(name) or {}).get("trade_count") or 0)
        if c < 15:
            recs.append(
                f"Need more {name.replace('_', ' ').title()} session samples "
                f"(have {c})"
            )

    regs = regimes.get("regimes") or {}
    for name in ("trend", "range", "high_volatility", "low_volatility"):
        c = int((regs.get(name) or {}).get("trade_count") or 0)
        if c < 10:
            recs.append(f"Need more {name.replace('_', ' ')} regime samples (have {c})")

    if int(regimes.get("unlabeled_trades") or 0) > 0:
        recs.append("Persist regime labels on closed deals before trusting regime KPIs")

    if signals.get("status") in {"insufficient_tags", "unavailable"}:
        recs.append("Tag BOS/CHOCH/OB/FVG/sweep on journals for signal analytics")
    best = signals.get("best_combination")
    if isinstance(best, dict) and best.get("combination"):
        recs.append(
            f"Research focus: best tagged combination so far is "
            f"{best['combination']} (n={best.get('trade_count')}) — "
            "do not auto-change strategy"
        )

    if no_trade.get("status") != "available":
        recs.append("Collect Decision Engine NO_TRADE reasons for refusal analytics")

    wr = metrics.get("win_rate")
    pf = metrics.get("profit_factor")
    if wr is not None and wr < 0.4 and n >= 20:
        recs.append("Win rate below 40% on sample — review entry filters in research")
    if pf is not None and pf < 1.0 and n >= 20:
        recs.append("Profit factor below 1.0 on sample — review exits/RR in research")

    return list(dict.fromkeys(recs))


def build_performance_intelligence(
    *,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
    period: str = "monthly",
) -> dict[str, Any]:
    """Compose full Institutional Performance Intelligence dashboard."""
    merged = list(trades or [])
    if journal_rows:
        merged.extend(journal_rows)
    normalized = normalize_trade_rows(merged)
    decs = normalize_decision_rows(decisions)

    performance = compute_performance_dashboard(normalized)
    sessions = enrich_session_analytics(normalized)
    regimes = enrich_regime_analytics(normalized)
    signals = compute_signal_analytics(normalized)
    no_trade = compute_no_trade_analytics(decs)
    time_a = compute_time_analytics(normalized)
    report = build_period_report(
        normalized, period=period, decisions=decs
    )
    recs = build_recommendations(
        performance=performance,
        sessions=sessions,
        regimes=regimes,
        signals=signals,
        no_trade=no_trade,
    )

    return {
        "version": "1.0.1",
        "status": performance.get("status"),
        "performance": performance,
        "sessions": sessions,
        "regimes": regimes,
        "signals": signals,
        "no_trade": no_trade,
        "time": time_a,
        "report": report,
        "recommendations": recs,
        "evidence_summary": {
            "closed_trades_with_pnl": len(normalized),
            "raw_trade_rows": len(merged),
            "decisions": len(decs),
            "recommendation_count": len(recs),
            "period": period,
        },
        "never_modifies_strategy": True,
        "never_modifies_risk_safety_execution": True,
        "never_fabricates_metrics": True,
        "advisory_only": True,
    }
