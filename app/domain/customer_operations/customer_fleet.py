"""Customer Fleet Dashboard — all customers, filters, health."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_persistence import utc_iso
from app.domain.customer_operations.production_readers import (
    live_trading_health_snapshot,
    read_licenses,
    read_mt5_connections,
    read_users,
)


async def build_customer_fleet(
    *,
    country: str | None = None,
    broker: str | None = None,
    status: str | None = None,
    license_status: str | None = None,
) -> dict[str, Any]:
    users = await read_users()
    licenses = await read_licenses()
    mt5 = await read_mt5_connections()
    live = live_trading_health_snapshot()

    lic_by_user: dict[str, dict[str, Any]] = {}
    for lic in licenses:
        uid = str(lic.get("user_id") or "")
        if uid and uid not in lic_by_user:
            lic_by_user[uid] = lic

    mt5_by_user: dict[str, list[dict[str, Any]]] = {}
    for c in mt5:
        uid = str(c.get("user_id") or "")
        if uid:
            mt5_by_user.setdefault(uid, []).append(c)

    rows: list[dict[str, Any]] = []
    for u in users:
        uid = str(u.get("id") or "")
        lic = lic_by_user.get(uid) or {}
        conns = mt5_by_user.get(uid) or []
        primary = conns[0] if conns else {}
        status_l = str(primary.get("status")).lower()
        mt5_ok = bool(primary.get("connected")) or status_l in {
            "connected",
            "ok",
            "healthy",
        }
        row = {
            "customer_id": uid,
            "email": u.get("email"),
            "display_name": u.get("display_name"),
            "country": u.get("country"),
            "status": u.get("status"),
            "license": lic.get("status"),
            "license_tier": lic.get("tier"),
            "broker": primary.get("broker") or primary.get("server"),
            "robot_online": live.get("robot_online"),
            "gateway": live.get("gateway"),
            "mt5": "connected" if mt5_ok else ("disconnected" if primary else "none"),
            "ai": live.get("ai"),
            "oms": live.get("oms"),
            "open_positions": live.get("open_positions"),
            "pnl": live.get("pnl"),
            "risk_status": live.get("risk_status"),
            "last_signal": live.get("last_signal"),
            "health": (
                "healthy"
                if mt5_ok and str(lic.get("status") or "") in {"", "active"}
                else "attention"
            ),
            "fabricated": False,
        }
        rows.append(row)

    def _match(row: dict[str, Any]) -> bool:
        if country and str(row.get("country") or "").lower() != country.lower():
            return False
        if broker and broker.lower() not in str(row.get("broker") or "").lower():
            return False
        if status and str(row.get("status") or "").lower() != status.lower():
            return False
        lic = str(row.get("license") or "").lower()
        return not (license_status and lic != license_status.lower())

    filtered = [r for r in rows if _match(r)]
    return {
        "as_of": utc_iso(),
        "customers": filtered,
        "count": len(filtered),
        "total_unfiltered": len(rows),
        "filters": {
            "country": country,
            "broker": broker,
            "status": status,
            "license": license_status,
        },
        "fabricated": False,
        "source": "production_users_licenses_mt5",
        "trading_behaviour_unchanged": True,
    }
