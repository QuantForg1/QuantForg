"""Error / incident analytics — aggregation only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate_errors(
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate warning/error/critical/timeout/reconnect/retry/failure/recovery."""
    buckets = {
        "warnings": 0,
        "errors": 0,
        "critical_events": 0,
        "timeouts": 0,
        "reconnects": 0,
        "retries": 0,
        "failures": 0,
        "recovery_events": 0,
    }
    by_component: dict[str, int] = defaultdict(int)
    recent: list[dict[str, Any]] = []

    for raw in events or []:
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity") or "").lower()
        action = str(raw.get("action") or raw.get("type") or "").lower()
        result = str(raw.get("result") or raw.get("outcome") or "").lower()
        text = (
            f"{action} {result} {raw.get('notes') or ''} "
            f"{raw.get('reason') or ''}"
        ).lower()

        if severity == "warning" or "warn" in text:
            buckets["warnings"] += 1
        if severity == "error" or "error" in text:
            buckets["errors"] += 1
        if severity == "critical" or "critical" in text:
            buckets["critical_events"] += 1
        if "timeout" in text:
            buckets["timeouts"] += 1
        if "reconnect" in text:
            buckets["reconnects"] += 1
        if "retry" in text:
            buckets["retries"] += 1
        if "fail" in text or result in {"failure", "failed", "denied"}:
            buckets["failures"] += 1
        if "recover" in text:
            buckets["recovery_events"] += 1

        comp = str(raw.get("component") or raw.get("category") or "system")
        by_component[comp] += 1
        recent.append(
            {
                "timestamp": raw.get("timestamp"),
                "severity": severity or None,
                "action": action or None,
                "component": comp,
                "result": result or None,
            }
        )

    return {
        "status": "available" if events is not None else "unavailable",
        "totals": buckets,
        "by_component": dict(by_component),
        "recent": recent[-100:],
        "sample_size": len(events or []),
        "note": "Empty when no events supplied — never fabricates incidents",
        "observability_only": True,
    }
