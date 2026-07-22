"""EOD / weekly / monthly review builders — advisory only."""

from __future__ import annotations

from typing import Any


def _metrics(performance: dict[str, Any] | None) -> dict[str, Any]:
    block = dict(performance or {})
    if "metrics" in block and isinstance(block["metrics"], dict):
        return dict(block["metrics"])
    return block


def build_end_of_day_report(
    *,
    performance: dict[str, Any] | None = None,
    sessions: dict[str, Any] | None = None,
    no_trade: dict[str, Any] | None = None,
    evidence_summary: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    m = _metrics(performance)
    evidence = dict(evidence_summary or {})
    conf = dict(confidence or {})
    return {
        "status": "available" if m or evidence else "unavailable",
        "trades": m.get("total_trades"),
        "win_rate": m.get("win_rate"),
        "profit_factor": m.get("profit_factor"),
        "expectancy": m.get("expectancy"),
        "drawdown": m.get("maximum_drawdown_pct"),
        "session_breakdown": sessions or {"status": "unavailable"},
        "no_trade_summary": no_trade or {"status": "unavailable"},
        "replay_coverage": {
            "replay_opportunities": evidence.get("replay_opportunities"),
            "coverage": (
                (
                    (conf.get("lane_samples") or {}).get("replay_opportunities") or {}
                ).get("coverage")
            ),
        },
        "evidence_growth": {
            "live_records": evidence.get("live_records"),
            "demo_records": evidence.get("demo_records"),
            "replay_opportunities": evidence.get("replay_opportunities"),
            "research_records": evidence.get("research_records"),
            "no_trade_observations": evidence.get("no_trade_observations"),
        },
        "note": "EOD aggregates supplied Performance IQ + Evidence Lab facts only",
        "never_fabricates_metrics": True,
    }


def _week_snapshot(
    label: str,
    performance: dict[str, Any] | None,
) -> dict[str, Any]:
    m = _metrics(performance)
    return {
        "label": label,
        "status": "available" if m.get("total_trades") is not None else "unavailable",
        "trades": m.get("total_trades"),
        "win_rate": m.get("win_rate"),
        "profit_factor": m.get("profit_factor"),
        "expectancy": m.get("expectancy"),
        "drawdown": m.get("maximum_drawdown_pct"),
        "net_pnl": m.get("net_pnl"),
    }


def _delta(curr: Any, prev: Any) -> float | None:
    if curr is None or prev is None:
        return None
    try:
        return round(float(curr) - float(prev), 6)
    except (TypeError, ValueError):
        return None


def build_weekly_review(
    *,
    current_week: dict[str, Any] | None = None,
    previous_week: dict[str, Any] | None = None,
) -> dict[str, Any]:
    curr = _week_snapshot("current_week", current_week)
    prev = _week_snapshot("previous_week", previous_week)
    improvements: list[str] = []
    regressions: list[str] = []
    unknowns: list[str] = []

    comparisons = [
        ("win_rate", "Win rate", True),
        ("profit_factor", "Profit factor", True),
        ("expectancy", "Expectancy", True),
        ("drawdown", "Drawdown", False),
        ("net_pnl", "Net P/L", True),
    ]
    for key, label, higher_better in comparisons:
        d = _delta(curr.get(key), prev.get(key))
        if d is None:
            unknowns.append(f"{label}: insufficient data to compare")
            continue
        if d == 0:
            unknowns.append(f"{label}: unchanged week-over-week")
            continue
        better = d > 0 if higher_better else d < 0
        msg = f"{label}: {prev.get(key)} → {curr.get(key)} (Δ {d:+})"
        if better:
            improvements.append(msg)
        else:
            regressions.append(msg)

    if curr["status"] == "unavailable":
        unknowns.append("Current week performance unavailable")
    if prev["status"] == "unavailable":
        unknowns.append("Previous week performance unavailable")

    return {
        "status": "available",
        "current_week": curr,
        "previous_week": prev,
        "improvements": improvements,
        "regressions": regressions,
        "unknowns": unknowns,
        "advisory_only": True,
        "never_suggests_strategy_changes": True,
    }


def build_monthly_review(
    *,
    performance: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    execution_quality: dict[str, Any] | None = None,
    evidence_summary: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    open_research_topics: list[str] | None = None,
) -> dict[str, Any]:
    m = _metrics(performance)
    evidence = dict(evidence_summary or {})
    conf = dict(confidence or {})
    topics = list(open_research_topics or [])
    if not topics:
        if evidence.get("gates_passed") is False:
            topics.append("Clear Evidence Lab gates before strategy-change research")
        if str(conf.get("overall_confidence") or "").lower() in {
            "insufficient",
            "low",
            "",
        }:
            topics.append("Grow sample size to raise overall confidence")
        if not topics:
            topics.append(
                "Confirm Live / Demo / Replay / Research lanes stay segregated"
            )

    return {
        "status": "available",
        "performance": {
            "trades": m.get("total_trades"),
            "win_rate": m.get("win_rate"),
            "profit_factor": m.get("profit_factor"),
            "expectancy": m.get("expectancy"),
            "drawdown": m.get("maximum_drawdown_pct"),
            "net_pnl": m.get("net_pnl"),
        },
        "risk": risk
        or {
            "maximum_drawdown_pct": m.get("maximum_drawdown_pct"),
            "recovery_factor": m.get("recovery_factor"),
            "note": "From supplied performance risk metrics only",
        },
        "execution_quality": execution_quality
        or {
            "status": "unavailable",
            "note": "Execution quality not supplied — never fabricated",
        },
        "evidence_growth": {
            "live_records": evidence.get("live_records"),
            "replay_opportunities": evidence.get("replay_opportunities"),
            "research_records": evidence.get("research_records"),
            "no_trade_observations": evidence.get("no_trade_observations"),
            "gates_passed": evidence.get("gates_passed"),
        },
        "confidence_growth": {
            "overall_confidence": conf.get("overall_confidence")
            or evidence.get("overall_confidence"),
            "lane_samples": conf.get("lane_samples"),
        },
        "open_research_topics": topics,
        "advisory_only": True,
        "never_suggests_strategy_changes": True,
    }
