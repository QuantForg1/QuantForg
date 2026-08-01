"""Performance monitoring — memory, CPU, network, DB, slow endpoints/queries."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability.persistence import utc_iso


def build_performance_monitoring(
    *,
    observability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    obs = observability or {}
    resources = obs.get("resources") if isinstance(obs.get("resources"), dict) else {}
    raw_lat = obs.get("latencies_ms")
    latencies = raw_lat if isinstance(raw_lat, dict) else {}

    slow_endpoints: list[dict[str, Any]] = []
    for name, ms in latencies.items():
        if ms is None:
            continue
        try:
            val = float(ms)
        except (TypeError, ValueError):
            continue
        if val >= 250.0:
            slow_endpoints.append(
                {
                    "endpoint_or_channel": str(name),
                    "latency_ms": val,
                    "threshold_ms": 250.0,
                }
            )
    slow_endpoints.sort(key=lambda r: float(r["latency_ms"]), reverse=True)

    # Slow queries — observe only; never invent query text
    slow_queries: list[dict[str, Any]] = []
    db_ms = latencies.get("database")
    if db_ms is not None:
        try:
            if float(db_ms) >= 100.0:
                slow_queries.append(
                    {
                        "channel": "database_probe",
                        "latency_ms": float(db_ms),
                        "note": (
                            "Probe latency elevated — query inventory not fabricated"
                        ),
                    }
                )
        except (TypeError, ValueError):
            pass

    return {
        "as_of": utc_iso(),
        "memory": {
            "percent": resources.get("memory_percent"),
            "mb": resources.get("memory_mb"),
        },
        "cpu": {"percent": resources.get("cpu_percent")},
        "network": {
            "bytes_sent": resources.get("network_bytes_sent"),
            "bytes_recv": resources.get("network_bytes_recv"),
            "open_connections": resources.get("open_connections"),
        },
        "database": {
            "latency_ms": latencies.get("database"),
            "disk_percent": resources.get("disk_percent"),
        },
        "slow_endpoints": slow_endpoints,
        "slow_queries": slow_queries,
        "resource_source": resources.get("source"),
        "fabricated": False,
        "observe_only": True,
    }
