"""Governance aggregations — dashboard, timeline, accountability, reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.audit_governance.change_history import ConfigurationChangeHistory
from app.domain.audit_governance.models import EVENT_CATEGORIES, HARD_LOCKS
from app.domain.audit_governance.store import ImmutableAuditStore
from app.domain.audit_governance.versions import TradeVersionRegistry


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def build_forensic_timeline(
    events: list[dict[str, Any]],
    *,
    limit: int = 100,
) -> dict[str, Any]:
    rows = sorted(events, key=lambda e: str(e.get("timestamp") or ""))
    if limit:
        rows = rows[-limit:]
    steps = [
        {
            "timestamp": e.get("timestamp"),
            "action": e.get("action"),
            "category": e.get("category"),
            "severity": e.get("severity"),
            "actor": e.get("actor"),
            "previous_state": e.get("previous_state"),
            "new_state": e.get("new_state"),
            "result": e.get("result"),
            "event_id": e.get("event_id"),
        }
        for e in rows
    ]
    return {
        "status": "available" if steps else "unavailable",
        "count": len(steps),
        "steps": steps,
        "note": "Chronological forensic replay of audit history — read-only",
    }


def build_operator_accountability(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    sensitive = {
        "ops_promotion",
        "execution_enabled",
        "execution_disabled",
        "kill_switch_armed",
        "kill_switch_disarmed",
        "emergency_stop",
        "configuration_updated",
    }
    rows = [
        {
            "event_id": e.get("event_id"),
            "timestamp": e.get("timestamp"),
            "action": e.get("action"),
            "actor": e.get("actor"),
            "reason": e.get("reason"),
            "approval": e.get("approval"),
            "result": e.get("result"),
            "previous_state": e.get("previous_state"),
            "new_state": e.get("new_state"),
        }
        for e in events
        if str(e.get("action") or "") in sensitive
    ]
    by_actor: dict[str, int] = {}
    for r in rows:
        actor = str(r.get("actor") or "unknown")
        by_actor[actor] = by_actor.get(actor, 0) + 1
    return {
        "status": "available" if rows else "unavailable",
        "sensitive_actions": len(rows),
        "by_actor": by_actor,
        "items": rows[-200:],
        "note": "Who / when / why / approval / result — governance only",
    }


def build_governance_dashboard(
    *,
    store: ImmutableAuditStore,
    config_history: ConfigurationChangeHistory,
    versions: TradeVersionRegistry,
    limit: int = 200,
) -> dict[str, Any]:
    events = store.list(limit=max(limit, 500))
    critical = [e for e in events if e.get("severity") == "critical"]
    warnings = [e for e in events if e.get("severity") == "warning"]
    recent = events[-min(limit, len(events)) :] if events else []
    by_category = dict.fromkeys(EVENT_CATEGORIES, 0)
    for e in events:
        cat = str(e.get("category") or "system")
        if cat in by_category:
            by_category[cat] += 1
        else:
            by_category["system"] = by_category.get("system", 0) + 1

    return {
        "version": "1.0.1",
        "status": "available",
        "governance_only": True,
        "hard_locks": HARD_LOCKS,
        "security": store.security_status(),
        "counts": {
            "total_events": store.count(),
            "critical": len(critical),
            "warnings": len(warnings),
            "config_changes": config_history.count(),
            "trade_version_tags": len(versions.list(limit=100_000)),
        },
        "by_category": by_category,
        "recent_events": recent[-50:],
        "critical_events": critical[-50:],
        "warnings": warnings[-50:],
        "timeline": build_forensic_timeline(events, limit=40),
        "accountability": build_operator_accountability(events),
        "filters": {
            "categories": list(EVENT_CATEGORIES),
            "severities": ["info", "warning", "critical"],
        },
    }


def _period_events(
    events: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in events:
        ts = _parse_ts(e.get("timestamp"))
        if ts is None:
            continue
        if start <= ts <= end:
            out.append(e)
    return out


def build_daily_audit_report(
    events: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day = _period_events(events, start=start, end=now)
    return {
        "report": "daily_audit",
        "period_start": start.isoformat().replace("+00:00", "Z"),
        "period_end": now.isoformat().replace("+00:00", "Z"),
        "event_count": len(day),
        "critical_count": sum(1 for e in day if e.get("severity") == "critical"),
        "warning_count": sum(1 for e in day if e.get("severity") == "warning"),
        "actions": dict(Counter(str(e.get("action") or "") for e in day)),
        "events": day,
        "governance_only": True,
    }


def build_weekly_governance_report(
    events: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(UTC)
    start = now - timedelta(days=7)
    week = _period_events(events, start=start, end=now)
    return {
        "report": "weekly_governance",
        "period_start": start.isoformat().replace("+00:00", "Z"),
        "period_end": now.isoformat().replace("+00:00", "Z"),
        "event_count": len(week),
        "by_category": dict(Counter(str(e.get("category") or "") for e in week)),
        "by_severity": dict(Counter(str(e.get("severity") or "") for e in week)),
        "top_actors": dict(
            Counter(str(e.get("actor") or "") for e in week).most_common(10)
        ),
        "governance_only": True,
    }


def build_monthly_compliance_report(
    events: list[dict[str, Any]],
    config_changes: list[dict[str, Any]],
    version_tags: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(UTC)
    start = now - timedelta(days=30)
    month = _period_events(events, start=start, end=now)
    return {
        "report": "monthly_compliance",
        "period_start": start.isoformat().replace("+00:00", "Z"),
        "period_end": now.isoformat().replace("+00:00", "Z"),
        "event_count": len(month),
        "critical_events": [e for e in month if e.get("severity") == "critical"],
        "config_changes": len(config_changes),
        "trade_version_tags": len(version_tags),
        "compliance_notes": [
            "Audit store is append-only and immutable",
            "Configuration history never overwrites prior entries",
            "Trade version tags permanently record strategy/risk/safety/execution",
        ],
        "governance_only": True,
    }


def build_critical_event_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    critical = [e for e in events if e.get("severity") == "critical"]
    return {
        "report": "critical_events",
        "count": len(critical),
        "events": critical,
        "governance_only": True,
    }


def build_configuration_change_report(
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "report": "configuration_changes",
        "count": len(changes),
        "changes": changes,
        "never_overwrite_history": True,
        "governance_only": True,
    }


def build_recommendations(
    *,
    dashboard: dict[str, Any],
    security: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    counts = dashboard.get("counts") or {}
    if int(counts.get("total_events") or 0) == 0:
        recs.append("Ingest institutional ops events into the audit trail")
    if int(counts.get("critical") or 0) > 0:
        recs.append(
            f"Review {counts['critical']} critical governance events "
            "(accountability only — no strategy changes)"
        )
    if not security.get("chronological"):
        recs.append("Investigate non-chronological audit ordering")
    if int(counts.get("config_changes") or 0) == 0:
        recs.append("Record production configuration changes with actor and reason")
    if int(counts.get("trade_version_tags") or 0) == 0:
        recs.append(
            "Tag closed trades with strategy/risk/safety/execution/"
            "configuration versions"
        )
    recs.append(
        "Never modify strategy, risk, safety, execution, Performance IQ, "
        "Evidence Lab, or Trading Operations Center from governance"
    )
    return recs


def build_audit_governance_pack(
    *,
    store: ImmutableAuditStore,
    config_history: ConfigurationChangeHistory,
    versions: TradeVersionRegistry,
    limit: int = 500,
) -> dict[str, Any]:
    events = store.list(limit=limit)
    changes = config_history.list(limit=limit)
    tags = versions.list(limit=limit)
    dashboard = build_governance_dashboard(
        store=store,
        config_history=config_history,
        versions=versions,
        limit=limit,
    )
    reports = {
        "daily_audit_report": build_daily_audit_report(events),
        "weekly_governance_report": build_weekly_governance_report(events),
        "monthly_compliance_report": build_monthly_compliance_report(
            events, changes, tags
        ),
        "critical_event_report": build_critical_event_report(events),
        "configuration_change_report": build_configuration_change_report(changes),
    }
    security = store.security_status()
    recommendations = build_recommendations(dashboard=dashboard, security=security)
    return {
        "version": "1.0.1",
        "status": "available",
        "governance_only": True,
        "never_modifies_trading_behaviour": True,
        "hard_locks": HARD_LOCKS,
        "dashboard": dashboard,
        "timeline": dashboard.get("timeline"),
        "accountability": dashboard.get("accountability"),
        "change_history": changes,
        "trade_versions": tags,
        "reports": reports,
        "security": security,
        "recommendations": recommendations,
        "evidence_summary": {
            "total_events": store.count(),
            "critical": (dashboard.get("counts") or {}).get("critical"),
            "warnings": (dashboard.get("counts") or {}).get("warnings"),
            "config_changes": config_history.count(),
            "trade_version_tags": len(tags),
            "append_only": True,
            "immutable": True,
        },
    }
