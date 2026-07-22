"""Observability reports — health / reliability / stability / incidents."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_observability.alerts import detect_alerts
from app.domain.institutional_observability.dependency import build_dependency_map
from app.domain.institutional_observability.errors import aggregate_errors
from app.domain.institutional_observability.health import probe_components
from app.domain.institutional_observability.latency import collect_latencies
from app.domain.institutional_observability.metrics import (
    collect_resource_metrics,
    compute_uptime,
)
from app.domain.institutional_observability.models import HARD_LOCKS


def build_daily_health_report(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "report": "daily_health",
        "period": "24h",
        "overall": (pack.get("health") or {}).get("overall"),
        "component_counts": (pack.get("health") or {}).get("counts"),
        "uptime": pack.get("uptime"),
        "alert_count": (pack.get("alerts") or {}).get("count"),
        "observability_only": True,
    }


def build_weekly_reliability_report(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "report": "weekly_reliability",
        "period": "7d",
        "uptime_7d_ratio": (pack.get("uptime") or {}).get("uptime_7d_ratio"),
        "error_totals": (pack.get("errors") or {}).get("totals"),
        "high_latency": (pack.get("latencies") or {}).get("high_latency"),
        "observability_only": True,
    }


def build_monthly_stability_report(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "report": "monthly_stability",
        "period": "30d",
        "uptime_30d_ratio": (pack.get("uptime") or {}).get("uptime_30d_ratio"),
        "restart_history": (pack.get("uptime") or {}).get("restart_history"),
        "resource_snapshot": pack.get("resources"),
        "observability_only": True,
    }


def build_incident_report(pack: dict[str, Any]) -> dict[str, Any]:
    alerts = (pack.get("alerts") or {}).get("alerts") or []
    critical_errors = [
        e
        for e in ((pack.get("errors") or {}).get("recent") or [])
        if e.get("severity") == "critical"
    ]
    return {
        "report": "incident",
        "alerts": alerts,
        "critical_errors": critical_errors,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "observability_only": True,
    }


def build_recommendations(pack: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    overall = (pack.get("health") or {}).get("overall")
    if overall in {"down", "degraded", "unknown"}:
        recs.append(f"Investigate system health overall={overall}")
    for alert in (pack.get("alerts") or {}).get("alerts") or []:
        recs.append(f"Alert: {alert.get('message')}")
    if not (pack.get("errors") or {}).get("sample_size"):
        recs.append("Supply governance/error events for richer error analytics")
    if (pack.get("latencies") or {}).get("measured_count", 0) < 3:
        recs.append("Provide latency samples for gateway/broker/decision paths")
    recs.append(
        "Observability only — never modify strategy, risk, safety, or execution"
    )
    return recs


def build_observability_pack(
    *,
    ops_facts: dict[str, Any] | None = None,
    latency_samples: dict[str, float | None] | None = None,
    error_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    health = probe_components(ops_facts=ops_facts)
    latencies = collect_latencies(samples=latency_samples)
    resources = collect_resource_metrics()
    # Best-effort queue depth from facts
    if ops_facts and ops_facts.get("queue_depth") is not None:
        resources["queue_depth"] = ops_facts.get("queue_depth")
    errors = aggregate_errors(error_events)
    uptime = compute_uptime()
    dependency = build_dependency_map(health)
    alerts = detect_alerts(
        health=health,
        latencies=latencies,
        resources=resources,
        errors=errors,
    )
    pack: dict[str, Any] = {
        "version": "1.0.1",
        "status": "available",
        "observability_only": True,
        "never_modifies_trading_behaviour": True,
        "hard_locks": HARD_LOCKS,
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "health": health,
        "latencies": latencies,
        "resources": resources,
        "errors": errors,
        "uptime": uptime,
        "dependency": dependency,
        "alerts": alerts,
    }
    reports = {
        "daily_health_report": build_daily_health_report(pack),
        "weekly_reliability_report": build_weekly_reliability_report(pack),
        "monthly_stability_report": build_monthly_stability_report(pack),
        "incident_report": build_incident_report(pack),
    }
    recommendations = build_recommendations(pack)
    pack["reports"] = reports
    pack["recommendations"] = recommendations
    pack["evidence_summary"] = {
        "overall": health.get("overall"),
        "components_healthy": (health.get("counts") or {}).get("healthy"),
        "components_total": (health.get("counts") or {}).get("total"),
        "alert_count": alerts.get("count"),
        "measured_latencies": latencies.get("measured_count"),
        "error_sample_size": errors.get("sample_size"),
        "current_uptime_seconds": uptime.get("current_uptime_seconds"),
        "observability_only": True,
    }
    return pack
