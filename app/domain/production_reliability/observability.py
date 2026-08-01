"""Production observability — live latency, rates, resources (observe-only)."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.production_reliability.models import LATENCY_CHANNELS
from app.domain.production_reliability.persistence import utc_iso


def _read_ops_metrics() -> dict[str, Any]:
    try:
        from core.di.container import get_container

        collector = getattr(get_container(), "metrics_collector", None)
        if collector is None:
            return {}
        snap = collector.snapshot()
        if hasattr(snap, "__dict__") and not isinstance(snap, dict):
            return {
                "request_count": getattr(snap, "request_count", None),
                "error_count": getattr(snap, "error_count", None),
                "error_rate": getattr(snap, "error_rate", None),
                "avg_latency_ms": getattr(snap, "avg_latency_ms", None),
                "job_count": getattr(snap, "job_count", None),
                "avg_job_duration_ms": getattr(snap, "avg_job_duration_ms", None),
                "throughput_per_minute": getattr(snap, "throughput_per_minute", None),
            }
        return snap if isinstance(snap, dict) else {}
    except Exception:
        return {}


def _read_institutional_latencies() -> dict[str, float | None]:
    try:
        from app.domain.institutional_observability.latency import collect_latencies

        pack = collect_latencies()
        raw = pack.get("latencies_ms") or {}
        out: dict[str, float | None] = {}
        for k, v in raw.items():
            if v is None:
                out[str(k)] = None
            else:
                try:
                    out[str(k)] = float(v)
                except (TypeError, ValueError):
                    out[str(k)] = None
        return out
    except Exception:
        return {}


def _read_resources() -> dict[str, Any]:
    try:
        from app.domain.institutional_observability.metrics import (
            collect_resource_metrics,
        )

        return collect_resource_metrics()
    except Exception:
        return {}


def _gateway_latency_from_health() -> float | None:
    try:
        from app.application.services.production_component_health import (
            collect_trading_component_health,
        )
        from core.config.settings import get_settings

        pack = collect_trading_component_health(get_settings())
        gw = pack.get("gateway") or {}
        evidence = gw.get("evidence") if isinstance(gw, dict) else {}
        if isinstance(evidence, dict) and evidence.get("latency_ms") is not None:
            return float(evidence["latency_ms"])
    except Exception:
        return None
    return None


def build_observability() -> dict[str, Any]:
    """Aggregate live latency / error / success / resource signals."""
    inst = _read_institutional_latencies()
    ops = _read_ops_metrics()
    resources = _read_resources()

    latencies: dict[str, float | None] = dict.fromkeys(LATENCY_CHANNELS)
    for src, dst in (
        ("api", "api"),
        ("gateway", "gateway"),
        ("execution", "execution"),
        ("broker", "mt5"),
        ("decision", "oms"),
        ("journal", "database"),
    ):
        if inst.get(src) is not None:
            latencies[dst] = inst[src]

    gw_lat = _gateway_latency_from_health()
    if gw_lat is not None:
        latencies["gateway"] = gw_lat

    if ops.get("avg_latency_ms") is not None and latencies["api"] is None:
        with contextlib.suppress(TypeError, ValueError):
            latencies["api"] = float(ops["avg_latency_ms"])

    if ops.get("avg_job_duration_ms") is not None:
        with contextlib.suppress(TypeError, ValueError):
            latencies["background_job"] = float(ops["avg_job_duration_ms"])

    # Queue depth is not latency; keep latency null unless a real sample exists
    qdepth = resources.get("queue_depth")

    error_rate = ops.get("error_rate")
    request_count = ops.get("request_count")
    error_count = ops.get("error_count")
    success_rate: float | None = None
    try:
        if error_rate is not None:
            success_rate = round(max(0.0, 1.0 - float(error_rate)), 6)
            error_rate = float(error_rate)
        elif request_count and error_count is not None:
            rc = float(request_count)
            ec = float(error_count)
            if rc > 0:
                error_rate = round(ec / rc, 6)
                success_rate = round(1.0 - error_rate, 6)
    except (TypeError, ValueError):
        pass

    measured = {k: v for k, v in latencies.items() if v is not None}
    high = {k: v for k, v in measured.items() if v >= 250.0}

    return {
        "as_of": utc_iso(),
        "latencies_ms": latencies,
        "measured_count": len(measured),
        "high_latency": high,
        "threshold_ms": 250.0,
        "error_rate": error_rate,
        "success_rate": success_rate,
        "request_count": request_count,
        "error_count": error_count,
        "queue_depth": qdepth,
        "resources": {
            "cpu_percent": resources.get("cpu_percent"),
            "memory_percent": resources.get("memory_percent"),
            "memory_mb": resources.get("memory_used_mb"),
            "disk_percent": resources.get("disk_percent"),
            "network_bytes_sent": resources.get("network_bytes_sent"),
            "network_bytes_recv": resources.get("network_bytes_recv"),
            "open_connections": resources.get("open_connections"),
            "source": resources.get("source"),
        },
        "note": "Null means not measured — never fabricated",
        "observability_only": True,
        "fabricated": False,
    }
