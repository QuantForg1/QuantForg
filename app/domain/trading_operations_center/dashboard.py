"""ITOC orchestrator — executive dashboard + full operations pack."""

from __future__ import annotations

from typing import Any

from app.domain.trading_operations_center.alerts import detect_operational_alerts
from app.domain.trading_operations_center.brief import build_daily_brief
from app.domain.trading_operations_center.checklist import build_operations_checklist
from app.domain.trading_operations_center.models import HARD_LOCKS
from app.domain.trading_operations_center.reports import (
    build_end_of_day_report,
    build_monthly_review,
    build_weekly_review,
)


def build_recommendations(
    *,
    checklist: dict[str, Any],
    alerts: dict[str, Any],
    evidence_summary: dict[str, Any] | None,
    confidence: dict[str, Any] | None,
) -> list[str]:
    recs: list[str] = []
    for fail in checklist.get("failures") or []:
        recs.append(
            f"Resolve {fail.get('label')}: {fail.get('how_to_resolve')}"
        )
    for alert in alerts.get("alerts") or []:
        recs.append(f"Ops alert [{alert.get('severity')}]: {alert.get('title')}")
    evidence = dict(evidence_summary or {})
    conf = dict(confidence or {})
    if evidence.get("gates_passed") is False:
        recs.append(
            "Evidence gates blocked — grow live/replay/NO_TRADE samples "
            "(do not change strategy)"
        )
    overall = str(
        conf.get("overall_confidence") or evidence.get("overall_confidence") or ""
    )
    if overall in {"insufficient", "low"}:
        recs.append(
            f"Confidence is {overall} — treat KPIs as provisional until samples grow"
        )
    if not recs:
        recs.append(
            "Operations appear clear — continue monitoring; no strategy changes"
        )
    recs.append(
        "Recommendations are operational only — never modify strategy, risk, "
        "safety, execution, Performance IQ, or Evidence Lab"
    )
    return recs


def build_executive_dashboard(
    *,
    checklist: dict[str, Any],
    performance: dict[str, Any] | None,
    evidence_summary: dict[str, Any] | None,
    confidence: dict[str, Any] | None,
    risk: dict[str, Any] | None,
    execution: dict[str, Any] | None,
    alerts: dict[str, Any],
    recommendations: list[str],
) -> dict[str, Any]:
    m = (performance or {}).get("metrics") or performance or {}
    evidence = dict(evidence_summary or {})
    conf = dict(confidence or {})
    return {
        "status": "available",
        "operations_status": {
            "all_passed": checklist.get("all_passed"),
            "passed_count": checklist.get("passed_count"),
            "total": checklist.get("total"),
            "failures": checklist.get("failures"),
        },
        "performance": {
            "trades": m.get("total_trades") if isinstance(m, dict) else None,
            "win_rate": m.get("win_rate") if isinstance(m, dict) else None,
            "profit_factor": m.get("profit_factor") if isinstance(m, dict) else None,
            "expectancy": m.get("expectancy") if isinstance(m, dict) else None,
        },
        "evidence": {
            "live_records": evidence.get("live_records"),
            "replay_opportunities": evidence.get("replay_opportunities"),
            "gates_passed": evidence.get("gates_passed"),
        },
        "confidence": {
            "overall": conf.get("overall_confidence")
            or evidence.get("overall_confidence"),
        },
        "risk": risk
        or {
            "maximum_drawdown_pct": m.get("maximum_drawdown_pct")
            if isinstance(m, dict)
            else None,
            "note": "From supplied metrics only",
        },
        "execution": execution
        or {
            "status": "unknown",
            "note": "Execution status from ops facts / checklist only",
        },
        "outstanding_actions": recommendations[:8],
        "open_alert_count": alerts.get("alert_count"),
    }


def build_trading_operations_center(
    *,
    ops_facts: dict[str, Any] | None = None,
    expected_sessions: list[str] | None = None,
    high_impact_news: list[dict[str, Any]] | None = None,
    calendar_available: bool | None = None,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
    previous_week_trades: list[dict[str, Any]] | None = None,
    evidence_pack: dict[str, Any] | None = None,
    performance_pack: dict[str, Any] | None = None,
    execution_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full ITOC pack. Consumes IQ/Lab outputs; never mutates them."""
    facts = dict(ops_facts or {})

    # Optional: build Performance IQ from trades without editing that package
    perf_pack = dict(performance_pack or {})
    if not perf_pack and (trades or journal_rows or decisions):
        from app.domain.performance_intelligence.dashboard import (
            build_performance_intelligence,
        )

        perf_pack = build_performance_intelligence(
            trades=trades,
            decisions=decisions,
            journal_rows=journal_rows,
            period="daily",
        )

    evidence_pack = dict(evidence_pack or {})
    evidence_summary = dict(evidence_pack.get("evidence_summary") or {})
    confidence = dict(evidence_pack.get("confidence") or {})
    if evidence_summary.get("overall_confidence") is None and confidence:
        evidence_summary["overall_confidence"] = confidence.get("overall_confidence")

    # Derive evidence_healthy for checklist when not explicitly set
    if facts.get("evidence_healthy") is None and evidence_summary:
        gates_ok = evidence_summary.get("gates_passed") is True
        overall = str(evidence_summary.get("overall_confidence") or "").lower()
        facts["evidence_healthy"] = gates_ok and overall in {"medium", "high"}
        facts.setdefault(
            "evidence_status",
            f"gates={'pass' if gates_ok else 'blocked'}; confidence={overall or 'n/a'}",
        )

    checklist = build_operations_checklist(facts)
    alerts = detect_operational_alerts(
        ops_facts=facts,
        evidence_summary=evidence_summary,
        confidence=confidence,
        decisions=decisions,
        journal_rows=journal_rows,
        performance=perf_pack.get("performance"),
    )
    brief = build_daily_brief(
        trading_date=facts.get("trading_date"),
        expected_sessions=expected_sessions,
        high_impact_news=high_impact_news,
        calendar_available=calendar_available,
        market_regime=facts.get("market_regime"),
        volatility_expectation=facts.get("volatility_expectation"),
        evidence_status={
            "status": "available" if evidence_summary else "unknown",
            **evidence_summary,
        },
        open_alerts=alerts.get("alerts"),
    )

    eod = build_end_of_day_report(
        performance=perf_pack.get("performance"),
        sessions=perf_pack.get("sessions"),
        no_trade=perf_pack.get("no_trade"),
        evidence_summary=evidence_summary,
        confidence=confidence,
    )

    prev_perf: dict[str, Any] | None = None
    if previous_week_trades:
        from app.domain.performance_intelligence.dashboard import (
            compute_performance_dashboard,
            normalize_trade_rows,
        )

        prev_perf = compute_performance_dashboard(
            normalize_trade_rows(previous_week_trades)
        )

    weekly = build_weekly_review(
        current_week=perf_pack.get("performance"),
        previous_week=prev_perf,
    )
    monthly = build_monthly_review(
        performance=perf_pack.get("performance"),
        evidence_summary=evidence_summary,
        confidence=confidence,
        execution_quality=execution_quality,
    )

    recommendations = build_recommendations(
        checklist=checklist,
        alerts=alerts,
        evidence_summary=evidence_summary,
        confidence=confidence,
    )
    executive = build_executive_dashboard(
        checklist=checklist,
        performance=perf_pack.get("performance"),
        evidence_summary=evidence_summary,
        confidence=confidence,
        risk=monthly.get("risk"),
        execution={
            "execution_enabled": facts.get("execution_enabled"),
            "ops_mode": facts.get("ops_mode"),
            "checklist_all_passed": checklist.get("all_passed"),
        },
        alerts=alerts,
        recommendations=recommendations,
    )

    return {
        "version": "1.0.1",
        "status": "available",
        "advisory_only": True,
        "hard_locks": HARD_LOCKS,
        "daily_brief": brief,
        "checklist": checklist,
        "end_of_day": eod,
        "weekly_review": weekly,
        "monthly_review": monthly,
        "operational_alerts": alerts,
        "executive_dashboard": executive,
        "recommendations": recommendations,
        "evidence_summary": evidence_summary,
        "performance_summary": {
            "status": (perf_pack.get("performance") or {}).get("status"),
            "metrics": (perf_pack.get("performance") or {}).get("metrics") or {},
        },
    }
