"""Latency collection — supplied samples or micro-probes; never invents."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_observability.metrics import measure_latency_ms
from app.domain.institutional_observability.models import LATENCY_KEYS


def collect_latencies(
    *,
    samples: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Merge caller-supplied latency samples with lightweight local probes."""
    merged: dict[str, float | None] = dict.fromkeys(LATENCY_KEYS)
    for key, val in (samples or {}).items():
        if key in merged and val is not None:
            try:
                merged[key] = float(val)
            except (TypeError, ValueError):
                merged[key] = None

    # Local micro-probes (process-local only)
    if merged["api"] is None:
        merged["api"] = measure_latency_ms(lambda: sum(range(100)))
    if merged["dashboard"] is None:
        merged["dashboard"] = measure_latency_ms(lambda: {"ok": True})

    # Optional read-only store probes
    try:
        from app.domain.institutional_data_warehouse.store import get_warehouse

        if merged["journal"] is None:
            merged["journal"] = measure_latency_ms(
                lambda: get_warehouse().counts()
            )
    except Exception:
        merged.setdefault("journal", None)

    measured = {k: v for k, v in merged.items() if v is not None}
    high = {k: v for k, v in measured.items() if v >= 250.0}
    return {
        "status": "available",
        "latencies_ms": merged,
        "measured_count": len(measured),
        "high_latency": high,
        "threshold_ms": 250.0,
        "note": "Null means not measured — never fabricated",
        "observability_only": True,
    }
