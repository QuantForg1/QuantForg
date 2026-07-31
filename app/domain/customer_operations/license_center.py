"""Institutional License Center — uses existing License rules only."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.customer_operations.cop_audit import record_cop_audit
from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    new_id,
    redact,
    utc_iso,
)
from app.domain.customer_operations.production_readers import read_licenses

_NOTES: JsonDocumentStore | None = None
_HISTORY: JsonDocumentStore | None = None


def _notes_store() -> JsonDocumentStore:
    global _NOTES
    if _NOTES is None:
        _NOTES = JsonDocumentStore("cop_license_notes.json", "notes")
    return _NOTES


def _history_store() -> JsonDocumentStore:
    global _HISTORY
    if _HISTORY is None:
        _HISTORY = JsonDocumentStore("cop_license_audit_history.json", "history")
    return _HISTORY


def _append_history(entry: dict[str, Any]) -> None:
    _history_store().append(entry)


async def build_license_center() -> dict[str, Any]:
    licenses = await read_licenses()
    notes = {str(n.get("license_id")): n for n in _notes_store().list(limit=2000)}
    enriched = []
    counts = {
        "pending": 0,
        "active": 0,
        "suspended": 0,
        "revoked": 0,
        "expired": 0,
        "other": 0,
    }
    for lic in licenses:
        status = str(lic.get("status") or "").lower()
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
        note = notes.get(str(lic.get("id")), {})
        enriched.append(
            {
                **lic,
                "internal_notes": note.get("internal_notes") or lic.get("notes") or "",
                "manual_approval_required": status == "pending",
            }
        )
    history = list(reversed(_history_store().list(limit=100)))
    return {
        "as_of": utc_iso(),
        "licenses": enriched,
        "count": len(enriched),
        "pending_licenses": [lic for lic in enriched if lic.get("status") == "pending"],
        "active_licenses": [lic for lic in enriched if lic.get("status") == "active"],
        "suspended": [lic for lic in enriched if lic.get("status") == "suspended"],
        "revoked": [lic for lic in enriched if lic.get("status") == "revoked"],
        "counts": counts,
        "audit_history": history,
        "modifies_licensing_rules": False,
        "fabricated": False,
        "source": "public.licenses",
    }


async def add_license_internal_note(
    *,
    license_id: str,
    note: str,
    operator: str,
    ip: str | None = None,
) -> dict[str, Any]:
    before = _notes_store().get(license_id) or {"license_id": license_id}
    row = {
        "id": license_id,
        "license_id": license_id,
        "internal_notes": str(note or "").strip(),
        "updated_by": operator,
        "updated_at": utc_iso(),
    }
    existing = _notes_store().get(license_id)
    if existing:
        updated = _notes_store().upsert(
            license_id, lambda _: {**row, "id": license_id}
        )
    else:
        updated = _notes_store().append(row)
    _append_history(
        {
            "id": new_id("licaud"),
            "timestamp": utc_iso(),
            "license_id": license_id,
            "action": "internal_note",
            "operator": operator,
        }
    )
    record_cop_audit(
        operator=operator,
        action="license_internal_note",
        target=license_id,
        before=before,
        after=updated,
        ip=ip,
    )
    return redact(updated or row)


async def license_manual_action(
    *,
    license_id: str,
    action: str,
    operator: str,
    ip: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Activate / suspend / revoke via existing License aggregate methods only."""
    action_n = str(action or "").strip().lower()
    if action_n not in {"activate", "suspend", "revoke"}:
        return {
            "ok": False,
            "error": "unsupported_action",
            "allowed": ["activate", "suspend", "revoke"],
        }

    try:
        from core.di.container import get_container

        factory = getattr(get_container(), "platform_uow_factory", None) or getattr(
            get_container(), "uow_factory", None
        )
        if factory is None:
            return {"ok": False, "error": "uow_unavailable"}

        async with factory() as uow:
            lic = await uow.licenses.get_by_id(UUID(license_id))
            if lic is None:
                return {"ok": False, "error": "license_not_found"}
            before = lic.to_dict()
            if action_n == "activate":
                lic.activate()
            elif action_n == "suspend":
                lic.suspend()
            else:
                lic.revoke(reason=reason or "COP manual revoke")
            await uow.licenses.update(lic)
            await uow.commit()
            after = lic.to_dict()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "modifies_licensing_rules": False}

    _append_history(
        {
            "id": new_id("licaud"),
            "timestamp": utc_iso(),
            "license_id": license_id,
            "action": action_n,
            "operator": operator,
            "reason": reason,
        }
    )
    record_cop_audit(
        operator=operator,
        action=f"license_{action_n}",
        target=license_id,
        before=before,
        after=after,
        ip=ip,
    )
    return {
        "ok": True,
        "license": redact(after),
        "action": action_n,
        "modifies_licensing_rules": False,
        "used_existing_domain_methods": True,
    }


def license_health_summary(
    licenses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = licenses or []
    active = sum(1 for row in rows if str(row.get("status")) == "active")
    pending = sum(1 for row in rows if str(row.get("status")) == "pending")
    suspended = sum(1 for row in rows if str(row.get("status")) == "suspended")
    revoked = sum(1 for row in rows if str(row.get("status")) == "revoked")
    return {
        "active": active,
        "pending": pending,
        "suspended": suspended,
        "revoked": revoked,
        "total": len(rows),
        "health": "ok" if pending == 0 and suspended == 0 else "attention",
        "fabricated": False,
    }
