"""Normalize warehouse records — never invent missing production facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def normalize_warehouse_record(
    raw: dict[str, Any],
    *,
    domain: str,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """Map a source row into a warehouse record. Returns None if not a dict."""
    if not isinstance(raw, dict):
        return None

    ts = _parse_ts(
        raw.get("timestamp")
        or raw.get("occurred_at")
        or raw.get("opened_at")
        or raw.get("created_at")
        or raw.get("submitted_at")
    )
    versions = raw.get("versions") if isinstance(raw.get("versions"), dict) else {}

    def _ver(key: str, flat: str) -> str | None:
        if versions.get(key) is not None:
            return str(versions[key])
        if raw.get(flat) is not None:
            return str(raw.get(flat))
        if raw.get(f"{key}_version") is not None:
            return str(raw.get(f"{key}_version"))
        return None

    record = {
        "warehouse_id": str(raw.get("warehouse_id") or uuid4()),
        "domain": domain,
        "timestamp": _iso(ts) if ts else None,
        "correlation_id": (
            str(raw["correlation_id"])
            if raw.get("correlation_id") is not None
            else None
        ),
        "trade_id": (
            str(raw.get("trade_id") or raw.get("id") or raw.get("order_id") or "")
            or None
        ),
        "session": raw.get("session") or raw.get("market_session"),
        "symbol": raw.get("symbol") or raw.get("instrument") or "XAUUSD",
        "environment": environment
        or raw.get("environment")
        or raw.get("evidence_lane")
        or "unknown",
        "strategy_version": _ver("strategy", "strategy_version"),
        "risk_version": _ver("risk", "risk_version"),
        "safety_version": _ver("safety", "safety_version"),
        "execution_version": _ver("execution", "execution_version"),
        "payload": dict(raw),
        "read_only": True,
        "source_mutated": False,
    }
    return record
