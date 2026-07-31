"""Immutable COP enterprise audit — append-only, never mutates trading."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    fingerprint,
    new_id,
    redact,
    utc_iso,
)

_STORE: JsonDocumentStore | None = None


def get_cop_audit_store() -> JsonDocumentStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonDocumentStore("cop_audit_events.json", "events")
    return _STORE


def record_cop_audit(
    *,
    operator: str,
    action: str,
    target: str,
    before: Any = None,
    after: Any = None,
    ip: str | None = None,
    category: str = "customer_ops",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Every administrative action must generate an immutable audit record."""
    record = {
        "id": new_id("aud"),
        "timestamp": utc_iso(),
        "operator": str(operator or "system"),
        "action": str(action or "").strip().lower(),
        "target": str(target or ""),
        "before": redact(before),
        "after": redact(after),
        "ip": str(ip or "") or None,
        "category": category,
        "immutable": True,
        "append_only": True,
        "fingerprint": None,
        "extras": redact(extras or {}),
        "trading_impact": False,
        "modifies_ai": False,
        "modifies_oms": False,
        "modifies_mt5": False,
        "modifies_risk": False,
    }
    record["fingerprint"] = fingerprint(
        {
            "id": record["id"],
            "timestamp": record["timestamp"],
            "operator": record["operator"],
            "action": record["action"],
            "target": record["target"],
        }
    )
    return get_cop_audit_store().append(record)


def list_cop_audit(*, limit: int = 200) -> dict[str, Any]:
    rows = list(reversed(get_cop_audit_store().list(limit=limit)))
    return {
        "count": len(rows),
        "items": rows,
        "immutable": True,
        "append_only": True,
        "fabricated": False,
    }
