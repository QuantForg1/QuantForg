"""Retention policy — raw events / aggregates / archive (warehouse copies only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, RETENTION_TIERS
from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse

# Advisory defaults (days). Does not delete production data.
DEFAULT_POLICY: dict[str, Any] = {
    "raw_events_days": 90,
    "aggregates_days": 365,
    "archive_days": 1825,
    "never_deletes_production": True,
}


def apply_retention_classification(
    wh: InstitutionalDataWarehouse,
    *,
    policy: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify warehouse copies into retention tiers — never touches production."""
    pol = {**DEFAULT_POLICY, **(policy or {})}
    now = now or datetime.now(UTC)
    raw_cut = now - timedelta(days=int(pol["raw_events_days"]))
    agg_cut = now - timedelta(days=int(pol["aggregates_days"]))

    moved = {"raw_events": 0, "aggregates": 0, "archive": 0}
    for domain in DATA_DOMAINS:
        rows = wh.list(domain, limit=50_000)  # type: ignore[arg-type]
        classified: list[dict[str, Any]] = []
        for row in rows:
            ts_raw = row.get("timestamp")
            tier = "raw_events"
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    if ts < agg_cut:
                        tier = "archive"
                    elif ts < raw_cut:
                        tier = "aggregates"
                except ValueError:
                    tier = "raw_events"
            row = dict(row)
            row["retention_tier"] = tier
            classified.append(row)
            moved[tier] = moved.get(tier, 0) + 1
        wh.replace_rows(domain, classified)  # type: ignore[arg-type]

    return {
        "status": "available",
        "policy": pol,
        "tier_counts": moved,
        "tiers": list(RETENTION_TIERS),
        "read_only": True,
        "never_deletes_production": True,
    }


def retention_status(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    counts = {"raw_events": 0, "aggregates": 0, "archive": 0, "unknown": 0}
    for domain in DATA_DOMAINS:
        for row in wh.list(domain, limit=50_000):  # type: ignore[arg-type]
            tier = str(row.get("retention_tier") or "raw_events")
            if tier not in counts:
                counts["unknown"] += 1
            else:
                counts[tier] += 1
    return {
        "status": "available",
        "policy": DEFAULT_POLICY,
        "tier_counts": counts,
        "read_only": True,
        "never_deletes_production": True,
    }
