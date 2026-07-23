"""Data Quality Monitor — missing / duplicates / ordering / latency / integrity."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_data_warehouse.models import DATA_DOMAINS
from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def run_data_quality_monitor(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    missing_events = 0
    missing_fields: dict[str, int] = defaultdict(int)
    duplicates = 0
    ordering_violations = 0
    latency_samples: list[float] = []
    seen_ids: set[str] = set()
    scanned = 0
    empty_domains: list[str] = []

    required = ("uuid", "timestamp", "source", "correlation_id", "session", "trading_day", "environment")

    for domain in DATA_DOMAINS:
        rows = wh.list(domain, limit=20_000)  # type: ignore[arg-type]
        if not rows:
            empty_domains.append(domain)
            continue
        prev_ts: datetime | None = None
        for row in rows:
            scanned += 1
            uid = str(row.get("uuid") or row.get("warehouse_id") or "")
            if uid:
                key = f"{domain}:{uid}"
                if key in seen_ids:
                    duplicates += 1
                else:
                    seen_ids.add(key)
            else:
                missing_fields["uuid"] += 1
                missing_events += 1

            for field in required:
                if not row.get(field):
                    missing_fields[field] += 1

            ts = _parse_ts(row.get("timestamp"))
            if ts and prev_ts and ts < prev_ts:
                ordering_violations += 1
            if ts:
                prev_ts = ts
                # Latency proxy: age of event vs now (observability only)
                age = (datetime.now(UTC) - ts).total_seconds()
                if age >= 0:
                    latency_samples.append(age)

    avg_latency = (
        round(sum(latency_samples) / len(latency_samples), 2) if latency_samples else None
    )
    # Integrity score 0–100
    if scanned == 0:
        integrity = 0.0
    else:
        penalties = (
            missing_events * 2
            + duplicates * 3
            + ordering_violations * 2
            + sum(missing_fields.values()) * 0.05
            + len(empty_domains) * 0.5
        )
        integrity = max(0.0, min(100.0, 100.0 - penalties / max(scanned, 1) * 10.0))
        # boost if keyed well
        completeness = 1.0 - (sum(missing_fields.values()) / (scanned * len(required)))
        integrity = round(max(0.0, min(100.0, integrity * 0.5 + completeness * 50.0)), 2)

    return {
        "status": "available",
        "records_scanned": scanned,
        "missing_events": missing_events,
        "missing_fields": dict(missing_fields),
        "duplicates": duplicates,
        "ordering_violations": ordering_violations,
        "latency_seconds_avg": avg_latency,
        "empty_domains": empty_domains,
        "integrity_score": integrity,
        "read_only": True,
        "monitor": "data_quality",
    }
