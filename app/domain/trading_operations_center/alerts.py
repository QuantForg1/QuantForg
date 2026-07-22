"""Operational alerts — detect gaps; never suggest strategy changes."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _alert(
    *,
    code: str,
    severity: str,
    title: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "suggests_strategy_change": False,
    }


def detect_operational_alerts(
    *,
    ops_facts: dict[str, Any] | None = None,
    evidence_summary: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
    performance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect operational issues. Recommendations stay ops-only."""
    facts = dict(ops_facts or {})
    evidence = dict(evidence_summary or {})
    conf = dict(confidence or {})
    alerts: list[dict[str, Any]] = []

    live_n = int(
        evidence.get("live_records") or evidence.get("live_closed_trades") or 0
    )
    replay_n = int(
        evidence.get("replay_opportunities") or evidence.get("replay_records") or 0
    )
    overall = str(
        conf.get("overall_confidence") or evidence.get("overall_confidence") or ""
    ).lower()

    if live_n == 0 and replay_n == 0:
        alerts.append(
            _alert(
                code="missing_evidence",
                severity="high",
                title="Missing evidence",
                detail="No live or replay evidence records supplied",
            )
        )
    elif live_n == 0:
        alerts.append(
            _alert(
                code="missing_live_evidence",
                severity="medium",
                title="Missing live evidence",
                detail="Live evidence lane is empty",
            )
        )

    if overall in {"insufficient", "low", ""}:
        alerts.append(
            _alert(
                code="low_confidence",
                severity="medium" if overall == "low" else "high",
                title="Low confidence",
                detail=f"Overall confidence is '{overall or 'unknown'}'",
            )
        )

    gates_passed = evidence.get("gates_passed")
    if gates_passed is False or (
        isinstance(conf.get("lane_samples"), dict)
        and int(
            ((conf.get("lane_samples") or {}).get("replay_opportunities") or {}).get(
                "sample_size"
            )
            or 0
        )
        < 500
    ):
        coverage = (
            (conf.get("lane_samples") or {}).get("replay_opportunities") or {}
        ).get("coverage")
        if coverage is not None and float(coverage) < 1.0:
            alerts.append(
                _alert(
                    code="replay_backlog",
                    severity="medium",
                    title="Replay backlog",
                    detail=(
                        f"Replay coverage {coverage} below threshold — "
                        "ingest more historical opportunities"
                    ),
                )
            )

    journals = [j for j in (journal_rows or []) if isinstance(j, dict)]
    perf_n = int(
        ((performance or {}).get("metrics") or {}).get("total_trades")
        or ((performance or {}).get("sample_size") or 0)
    )
    if journals and perf_n == 0:
        alerts.append(
            _alert(
                code="journal_gaps",
                severity="medium",
                title="Journal gaps",
                detail=(
                    f"{len(journals)} journal rows supplied but none yielded "
                    "closed-trade PnL for performance"
                ),
            )
        )

    gw = facts.get("gateway_connected")
    if gw is False or str(gw).lower() in {"false", "0", "disconnected"}:
        alerts.append(
            _alert(
                code="gateway_instability",
                severity="high",
                title="Gateway instability",
                detail="Gateway reported disconnected / not connected",
            )
        )

    reasons: list[str] = []
    for d in decisions or []:
        if not isinstance(d, dict):
            continue
        action = str(d.get("decision") or d.get("action") or "").upper()
        if action != "NO_TRADE":
            continue
        reason = d.get("no_trade_reason") or d.get("reason") or d.get("why")
        if reason:
            reasons.append(str(reason))
    if reasons:
        counts = Counter(reasons)
        repeated = [(r, c) for r, c in counts.most_common(5) if c >= 2]
        if repeated:
            top = ", ".join(f"{r}x{c}" for r, c in repeated)
            alerts.append(
                _alert(
                    code="repeated_no_trade",
                    severity="low",
                    title="Repeated NO_TRADE causes",
                    detail=f"Recurring causes: {top} (ops awareness only)",
                )
            )

    return {
        "status": "available",
        "alert_count": len(alerts),
        "alerts": alerts,
        "never_suggests_strategy_changes": True,
        "note": "Alerts are operational only — never strategy-change proposals",
    }
