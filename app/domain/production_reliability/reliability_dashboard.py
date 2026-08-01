"""Reliability dashboard — availability, SLA/SLO, error budget, incidents."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability.models import (
    DEFAULT_SLA_AVAILABILITY,
    DEFAULT_SLO_AVAILABILITY,
)
from app.domain.production_reliability.persistence import utc_iso


def _incident_stats() -> dict[str, Any]:
    try:
        from app.domain.production_reliability.incidents import list_incidents

        rows = list_incidents(limit=500)
    except Exception:
        rows = []

    open_like = [
        r
        for r in rows
        if str(r.get("status") or "") in {"open", "investigating", "mitigated"}
    ]
    resolved = [
        r for r in rows if str(r.get("status") or "") in {"resolved", "postmortem"}
    ]

    recovery_seconds: list[float] = []
    for r in resolved:
        try:
            opened = r.get("opened_at") or r.get("created_at")
            closed = r.get("resolved_at") or r.get("updated_at")
            if opened and closed:
                from datetime import datetime

                def _parse(s: str) -> datetime:
                    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))

                delta = (_parse(str(closed)) - _parse(str(opened))).total_seconds()
                if delta >= 0:
                    recovery_seconds.append(delta)
        except Exception:  # noqa: S112  # best-effort optional path
            continue

    mttr = (
        round(sum(recovery_seconds) / len(recovery_seconds), 1)
        if recovery_seconds
        else None
    )
    return {
        "incident_count": len(rows),
        "open_incidents": len(open_like),
        "resolved_incidents": len(resolved),
        "recovery_time_seconds_avg": mttr,
        "recovery_samples": len(recovery_seconds),
    }


def _availability_from_health(health: dict[str, Any]) -> float | None:
    components = health.get("components") or {}
    if not isinstance(components, dict) or not components:
        return None
    statuses = []
    for row in components.values():
        if isinstance(row, dict):
            statuses.append(str(row.get("status") or "unknown").lower())
        else:
            statuses.append(str(row).lower())
    if not statuses:
        return None
    good = sum(
        1
        for s in statuses
        if s
        in {
            "healthy",
            "ok",
            "up",
            "ready",
            "connected",
            "configured",
            "disabled",
            "external",
            "available",
        }
    )
    return round(100.0 * good / len(statuses), 3)


def build_reliability_dashboard(
    *,
    health: dict[str, Any] | None = None,
    observability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = health or {}
    obs = observability or {}
    availability = _availability_from_health(health)
    slo = DEFAULT_SLO_AVAILABILITY
    sla = DEFAULT_SLA_AVAILABILITY

    # Error budget remaining (%) relative to SLO over observed window
    error_budget_remaining: float | None = None
    if availability is not None:
        allowed_downtime_pct = 100.0 - slo
        used = max(0.0, slo - availability)
        if allowed_downtime_pct > 0:
            remaining = max(0.0, 100.0 * (1.0 - used / allowed_downtime_pct))
            error_budget_remaining = round(min(100.0, remaining), 2)
        else:
            error_budget_remaining = 100.0 if availability >= slo else 0.0

    failure_rate = obs.get("error_rate")
    success_rate = obs.get("success_rate")
    incidents = _incident_stats()

    sla_met = availability is not None and availability >= sla
    slo_met = availability is not None and availability >= slo

    return {
        "as_of": utc_iso(),
        "availability_percent": availability,
        "sla_target_percent": sla,
        "slo_target_percent": slo,
        "sla_met": sla_met if availability is not None else None,
        "slo_met": slo_met if availability is not None else None,
        "error_budget_remaining_percent": error_budget_remaining,
        "incident_count": incidents["incident_count"],
        "open_incidents": incidents["open_incidents"],
        "resolved_incidents": incidents["resolved_incidents"],
        "recovery_time_seconds_avg": incidents["recovery_time_seconds_avg"],
        "failure_rate": failure_rate,
        "success_rate": success_rate,
        "window": "rolling_health_snapshot",
        "note": "Availability derived from live component health — never fabricated",
        "fabricated": False,
        "observe_only": True,
    }
