"""System Administration console — links existing surfaces, observe-only."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.api_keys import list_api_keys
from app.domain.enterprise_platform.persistence import utc_iso
from app.domain.enterprise_platform.production_readers import (
    read_organizations,
    read_users,
)


async def build_admin_console() -> dict[str, Any]:
    users = await read_users()
    orgs = await read_organizations()
    keys = list_api_keys()

    license_counts: dict[str, Any] = {}
    try:
        from app.domain.customer_operations.license_center import (
            build_license_center,
        )

        lic = await build_license_center()
        license_counts = lic.get("counts") or {}
    except Exception:
        license_counts = {}

    broker_connected = None
    try:
        from app.domain.customer_operations.broker_center import (
            build_broker_connection_center,
        )

        brokers = await build_broker_connection_center()
        broker_connected = brokers.get("connected")
    except Exception:  # noqa: S110  # best-effort optional path
        pass

    return {
        "as_of": utc_iso(),
        "users": {"count": len(users), "sample": users[:25]},
        "organizations": {"count": len(orgs), "sample": orgs[:25]},
        "licenses": license_counts,
        "infrastructure": {
            "links": {
                "noc": "/admin/noc",
                "customer_ops": "/admin/customer-ops",
                "gateway_ops": "/cloud-ops",
                "audit_governance": "/audit-governance",
                "organizations": "/organizations",
            },
            "broker_fleet_connected": broker_connected,
            "api_keys_active": sum(
                1 for k in keys.get("keys") or [] if k.get("status") == "active"
            ),
        },
        "surfaces": [
            "Users",
            "Organizations",
            "Licenses",
            "Infrastructure",
            "Gateway",
            "OMS",
            "AI",
            "Broker Fleet",
            "NOC",
        ],
        "note": (
            "Admin Console observes and links existing production surfaces. "
            "It does not modify Trading, AI, OMS, MT5, or COP logic."
        ),
        "fabricated": False,
        "modifies_trading": False,
        "modifies_cop": False,
    }
