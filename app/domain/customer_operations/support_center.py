"""Support Operations Center — tickets, notes, timeline, audit."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_audit import record_cop_audit
from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    new_id,
    redact,
    utc_iso,
)

_TICKETS: JsonDocumentStore | None = None


def get_support_ticket_store() -> JsonDocumentStore:
    global _TICKETS
    if _TICKETS is None:
        _TICKETS = JsonDocumentStore("cop_support_tickets.json", "tickets")
    return _TICKETS


def build_support_center() -> dict[str, Any]:
    tickets = list(reversed(get_support_ticket_store().list(limit=500)))
    pending = [t for t in tickets if str(t.get("status")) == "pending"]
    return {
        "as_of": utc_iso(),
        "tickets": tickets,
        "pending_requests": pending,
        "count": len(tickets),
        "pending_count": len(pending),
        "fabricated": False,
        "observe_only_reads": False,
        "modifies_trading": False,
    }


def create_support_ticket(
    *,
    subject: str,
    customer_id: str | None,
    priority: str = "normal",
    operator: str,
    ip: str | None = None,
    body: str = "",
) -> dict[str, Any]:
    ticket = {
        "id": new_id("sup"),
        "created_at": utc_iso(),
        "updated_at": utc_iso(),
        "subject": str(subject or "").strip() or "Support request",
        "customer_id": customer_id,
        "priority": str(priority or "normal").lower(),
        "status": "pending",
        "assigned_staff": None,
        "internal_notes": [],
        "resolution_timeline": [
            {
                "at": utc_iso(),
                "event": "created",
                "by": operator,
            }
        ],
        "attachments": [],
        "audit_log": [],
        "body": str(body or ""),
    }
    saved = get_support_ticket_store().append(ticket)
    record_cop_audit(
        operator=operator,
        action="support_ticket_create",
        target=saved["id"],
        before=None,
        after={"id": saved["id"], "subject": saved["subject"]},
        ip=ip,
    )
    return redact(saved)


def update_support_ticket(
    *,
    ticket_id: str,
    operator: str,
    ip: str | None = None,
    status: str | None = None,
    assigned_staff: str | None = None,
    priority: str | None = None,
    internal_note: str | None = None,
    attachment_name: str | None = None,
) -> dict[str, Any] | None:
    before = get_support_ticket_store().get(ticket_id)
    if before is None:
        return None

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        if status:
            row["status"] = str(status).lower()
            row.setdefault("resolution_timeline", []).append(
                {"at": utc_iso(), "event": f"status:{row['status']}", "by": operator}
            )
        if assigned_staff is not None:
            row["assigned_staff"] = assigned_staff
            row.setdefault("resolution_timeline", []).append(
                {
                    "at": utc_iso(),
                    "event": f"assigned:{assigned_staff}",
                    "by": operator,
                }
            )
        if priority:
            row["priority"] = str(priority).lower()
        if internal_note:
            row.setdefault("internal_notes", []).append(
                {"at": utc_iso(), "by": operator, "note": internal_note}
            )
        if attachment_name:
            # Metadata only — no binary storage of secrets
            row.setdefault("attachments", []).append(
                {
                    "at": utc_iso(),
                    "name": str(attachment_name)[:200],
                    "by": operator,
                }
            )
        row.setdefault("audit_log", []).append(
            {
                "at": utc_iso(),
                "by": operator,
                "action": "update",
            }
        )
        return row

    updated = get_support_ticket_store().upsert(ticket_id, mutator)
    record_cop_audit(
        operator=operator,
        action="support_ticket_update",
        target=ticket_id,
        before={
            "status": before.get("status"),
            "assigned": before.get("assigned_staff"),
        },
        after={
            "status": (updated or {}).get("status"),
            "assigned": (updated or {}).get("assigned_staff"),
        },
        ip=ip,
    )
    return updated
