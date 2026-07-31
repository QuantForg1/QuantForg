"""COP enterprise analytics — production data only, never fabricate revenue."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.broker_center import build_broker_connection_center
from app.domain.customer_operations.cop_persistence import utc_iso
from app.domain.customer_operations.license_center import build_license_center
from app.domain.customer_operations.production_readers import (
    live_trading_health_snapshot,
    read_users,
)
from app.domain.customer_operations.support_center import build_support_center


async def build_enterprise_analytics() -> dict[str, Any]:
    users = await read_users()
    licenses = await build_license_center()
    brokers = await build_broker_connection_center()
    support = build_support_center()
    live = live_trading_health_snapshot()

    active_customers = sum(
        1
        for u in users
        if str(u.get("status") or "").lower()
        in {"active", "enabled", ""}
    )
    # Countries unknown until profile enrichment — report null, never invent
    countries: list[str] = sorted(
        {str(u.get("country")) for u in users if u.get("country")}
    )

    return {
        "as_of": utc_iso(),
        "active_customers": active_customers,
        "total_customers": len(users),
        "active_robots": 1 if live.get("robot_online") else 0,
        "connected_brokers": brokers.get("connected") or 0,
        "broker_connections": brokers.get("count") or 0,
        "countries": countries,
        "countries_count": len(countries),
        "revenue": None,  # never fabricate — billing not in COP scope
        "revenue_note": "Revenue not fabricated; billing system not queried by COP",
        "support_metrics": {
            "total": support.get("count") or 0,
            "pending": support.get("pending_count") or 0,
        },
        "license_metrics": licenses.get("counts") or {},
        "fabricated": False,
        "source": "production_data_only",
        "trading_behaviour_unchanged": True,
    }
