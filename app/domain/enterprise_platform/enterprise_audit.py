"""Enterprise audit — immutable append-only records."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.persistence import (
    JsonDocumentStore,
    new_id,
    redact,
    utc_iso,
)

_STORE: JsonDocumentStore | None = None


def get_enterprise_audit_store() -> JsonDocumentStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonDocumentStore("enterprise_audit.json", "events")
    return _STORE


def record_enterprise_audit(
    *,
    operator: str,
    action: str,
    target: str,
    organization_id: str | None = None,
    before: Any = None,
    after: Any = None,
    ip: str | None = None,
    category: str = "enterprise",
) -> dict[str, Any]:
    row = {
        "id": new_id("eaud"),
        "timestamp": utc_iso(),
        "operator": str(operator or "system"),
        "action": str(action or "").strip().lower(),
        "target": str(target or ""),
        "organization_id": organization_id,
        "before": redact(before),
        "after": redact(after),
        "ip": ip,
        "category": category,
        "immutable": True,
        "append_only": True,
        "trading_impact": False,
    }
    return get_enterprise_audit_store().append(row)


def list_enterprise_audit(
    *,
    limit: int = 200,
    organization_id: str | None = None,
    action: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    rows = list(reversed(get_enterprise_audit_store().list(limit=limit * 3)))
    if organization_id:
        rows = [
            r for r in rows if str(r.get("organization_id") or "") == organization_id
        ]
    if action:
        rows = [r for r in rows if str(r.get("action") or "") == action.lower()]
    if q:
        ql = q.lower()
        rows = [
            r
            for r in rows
            if ql in str(r.get("operator") or "").lower()
            or ql in str(r.get("target") or "").lower()
            or ql in str(r.get("action") or "").lower()
        ]
    rows = rows[:limit]
    return {
        "count": len(rows),
        "items": rows,
        "immutable": True,
        "append_only": True,
        "fabricated": False,
    }
