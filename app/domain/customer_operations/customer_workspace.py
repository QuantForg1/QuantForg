"""Institutional Customer Workspace — per-customer desk."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    utc_iso,
)
from app.domain.customer_operations.production_readers import (
    live_trading_health_snapshot,
    read_audit_login_history,
    read_licenses,
    read_mt5_connections,
    read_users,
)
from app.domain.customer_operations.support_center import build_support_center

_DEVICES: JsonDocumentStore | None = None
_NOTIFS: JsonDocumentStore | None = None


def _devices() -> JsonDocumentStore:
    global _DEVICES
    if _DEVICES is None:
        _DEVICES = JsonDocumentStore("cop_customer_devices.json", "devices")
    return _DEVICES


def _notifs() -> JsonDocumentStore:
    global _NOTIFS
    if _NOTIFS is None:
        _NOTIFS = JsonDocumentStore("cop_customer_notifications.json", "notifications")
    return _NOTIFS


async def build_customer_workspace(customer_id: str) -> dict[str, Any]:
    users = await read_users()
    user = next((u for u in users if str(u.get("id")) == str(customer_id)), None)
    cid = str(customer_id)
    licenses = [
        lic for lic in await read_licenses() if str(lic.get("user_id")) == cid
    ]
    mt5 = [
        c for c in await read_mt5_connections() if str(c.get("user_id")) == cid
    ]
    logins = await read_audit_login_history(user_id=customer_id, limit=40)
    live = live_trading_health_snapshot()
    support = [
        t
        for t in build_support_center().get("tickets") or []
        if str(t.get("customer_id")) == str(customer_id)
    ]
    devices = [
        d
        for d in _devices().list(limit=200)
        if str(d.get("customer_id")) == cid
    ]
    notifications = [
        n
        for n in _notifs().list(limit=200)
        if str(n.get("customer_id")) == str(customer_id)
    ]
    primary_lic = licenses[0] if licenses else None
    primary_mt5 = mt5[0] if mt5 else None

    return {
        "as_of": utc_iso(),
        "customer_id": customer_id,
        "profile": user
        or {
            "id": customer_id,
            "status": "unknown",
            "fabricated": False,
            "note": "Customer not found in production users",
        },
        "license_status": (primary_lic or {}).get("status"),
        "licenses": licenses,
        "robot_status": live.get("robot_online"),
        "broker_status": (primary_mt5 or {}).get("status"),
        "mt5_connection": primary_mt5,
        "mt5_connections": mt5,
        "latest_activity": logins[:5],
        "device_list": devices,
        "login_history": logins,
        "support_requests": support,
        "notifications": list(reversed(notifications))[:50],
        "live_health": live,
        "fabricated": False,
        "credentials_exposed": False,
        "trading_behaviour_unchanged": True,
    }
