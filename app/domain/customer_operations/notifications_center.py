"""Institutional notification center — Customer / Operator / System / …"""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_audit import record_cop_audit
from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    new_id,
    redact,
    utc_iso,
)

CHANNELS = frozenset(
    {"customer", "operator", "system", "gateway", "trading", "security"}
)

_STORE: JsonDocumentStore | None = None


def get_cop_notification_store() -> JsonDocumentStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonDocumentStore("cop_notifications.json", "notifications")
    return _STORE


def build_notifications_center(*, channel: str | None = None) -> dict[str, Any]:
    rows = list(reversed(get_cop_notification_store().list(limit=500)))
    if channel:
        ch = channel.lower()
        rows = [r for r in rows if str(r.get("channel")).lower() == ch]
    by_channel: dict[str, int] = dict.fromkeys(sorted(CHANNELS), 0)
    for r in get_cop_notification_store().list(limit=2000):
        c = str(r.get("channel") or "system").lower()
        if c in by_channel:
            by_channel[c] += 1
    return {
        "as_of": utc_iso(),
        "notifications": rows,
        "count": len(rows),
        "by_channel": by_channel,
        "channels": sorted(CHANNELS),
        "fabricated": False,
    }


def publish_notification(
    *,
    channel: str,
    title: str,
    message: str,
    operator: str,
    customer_id: str | None = None,
    ip: str | None = None,
    severity: str = "info",
) -> dict[str, Any]:
    ch = str(channel or "system").lower()
    if ch not in CHANNELS:
        ch = "system"
    row = {
        "id": new_id("ntf"),
        "created_at": utc_iso(),
        "channel": ch,
        "title": str(title or "").strip() or "Notification",
        "message": str(message or "").strip(),
        "severity": str(severity or "info").lower(),
        "customer_id": customer_id,
        "created_by": operator,
        "read": False,
    }
    saved = get_cop_notification_store().append(row)
    record_cop_audit(
        operator=operator,
        action="notification_publish",
        target=saved["id"],
        before=None,
        after={"channel": ch, "title": saved["title"]},
        ip=ip,
    )
    return redact(saved)
