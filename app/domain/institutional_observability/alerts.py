"""Observability alerts — detection only; never changes trading behaviour."""

from __future__ import annotations

from typing import Any


def detect_alerts(
    *,
    health: dict[str, Any],
    latencies: dict[str, Any],
    resources: dict[str, Any],
    errors: dict[str, Any],
) -> dict[str, Any]:
    alerts: list[dict[str, Any]] = []

    comps = (health.get("components") or {}) if isinstance(health, dict) else {}
    gw = comps.get("gateway") or {}
    br = comps.get("broker") or {}
    if gw.get("status") == "down":
        alerts.append(
            {
                "id": "gateway_disconnect",
                "severity": "critical",
                "message": "Gateway disconnect detected",
            }
        )
    if br.get("status") == "down":
        alerts.append(
            {
                "id": "broker_disconnect",
                "severity": "critical",
                "message": "Broker disconnect detected",
            }
        )

    high = (
        (latencies.get("high_latency") or {})
        if isinstance(latencies, dict)
        else {}
    )
    for key, ms in high.items():
        alerts.append(
            {
                "id": f"high_latency_{key}",
                "severity": "warning",
                "message": f"High {key} latency: {ms} ms",
            }
        )

    totals = (errors.get("totals") or {}) if isinstance(errors, dict) else {}
    if int(totals.get("failures") or 0) >= 3:
        alerts.append(
            {
                "id": "repeated_failures",
                "severity": "warning",
                "message": f"Repeated failures: {totals.get('failures')}",
            }
        )

    qdepth = resources.get("queue_depth") if isinstance(resources, dict) else None
    if qdepth is not None and float(qdepth) >= 100:
        alerts.append(
            {
                "id": "queue_growth",
                "severity": "warning",
                "message": f"Queue depth elevated: {qdepth}",
            }
        )

    mem = resources.get("memory_percent") if isinstance(resources, dict) else None
    disk = resources.get("disk_percent") if isinstance(resources, dict) else None
    if mem is not None and float(mem) >= 90:
        alerts.append(
            {
                "id": "resource_exhaustion_memory",
                "severity": "critical",
                "message": f"Memory exhaustion risk: {mem}%",
            }
        )
    if disk is not None and float(disk) >= 90:
        alerts.append(
            {
                "id": "resource_exhaustion_disk",
                "severity": "critical",
                "message": f"Disk exhaustion risk: {disk}%",
            }
        )

    jw = comps.get("journal_writer") or {}
    if jw.get("status") in {"down", "degraded"}:
        alerts.append(
            {
                "id": "journal_failures",
                "severity": "warning",
                "message": "Journal writer unhealthy",
            }
        )
    wh = comps.get("warehouse") or {}
    if wh.get("status") in {"down", "degraded"}:
        alerts.append(
            {
                "id": "warehouse_failures",
                "severity": "warning",
                "message": "Warehouse unhealthy",
            }
        )

    return {
        "status": "available",
        "count": len(alerts),
        "alerts": alerts,
        "observability_only": True,
        "note": "Alert detection only — never auto-remediates trading systems",
    }
