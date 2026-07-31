"""Customer Operations Platform facade — additive ops only."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.analytics import build_enterprise_analytics
from app.domain.customer_operations.broker_center import build_broker_connection_center
from app.domain.customer_operations.cop_audit import list_cop_audit
from app.domain.customer_operations.cop_persistence import utc_iso
from app.domain.customer_operations.customer_fleet import build_customer_fleet
from app.domain.customer_operations.customer_workspace import build_customer_workspace
from app.domain.customer_operations.license_center import build_license_center
from app.domain.customer_operations.notifications_center import (
    build_notifications_center,
)
from app.domain.customer_operations.support_center import build_support_center


async def build_customer_operations_platform() -> dict[str, Any]:
    fleet = await build_customer_fleet()
    licenses = await build_license_center()
    brokers = await build_broker_connection_center()
    support = build_support_center()
    notifications = build_notifications_center()
    analytics = await build_enterprise_analytics()
    audit = list_cop_audit(limit=50)
    return {
        "as_of": utc_iso(),
        "fleet": fleet,
        "licenses": licenses,
        "brokers": brokers,
        "support": support,
        "notifications": notifications,
        "analytics": analytics,
        "audit": audit,
        "flags": {
            "modifies_trading": False,
            "modifies_ai": False,
            "modifies_oms": False,
            "modifies_mt5": False,
            "modifies_risk": False,
            "modifies_pricing": False,
            "modifies_licensing_rules": False,
            "credentials_exposed": False,
            "additive_only": True,
        },
        "fabricated": False,
    }


async def build_customer_ops_noc_panels() -> dict[str, Any]:
    """NOC observe-only COP panels — never touches trading intelligence modules."""
    try:
        fleet = await build_customer_fleet()
    except Exception:
        fleet = {"customers": [], "count": 0, "fabricated": False}
    try:
        licenses = await build_license_center()
    except Exception:
        licenses = {"counts": {}, "fabricated": False}
    try:
        brokers = await build_broker_connection_center()
    except Exception:
        brokers = {"count": 0, "connected": 0, "fabricated": False}
    try:
        support = build_support_center()
    except Exception:
        support = {"pending_count": 0, "fabricated": False}
    try:
        analytics = await build_enterprise_analytics()
    except Exception:
        analytics = {"fabricated": False}

    return {
        "customer_fleet": {
            "count": fleet.get("count") or 0,
            "rows": (fleet.get("customers") or [])[:12],
            "observe_only": True,
        },
        "license_health": {
            "counts": licenses.get("counts") or {},
            "pending": len(licenses.get("pending_licenses") or []),
            "health": (
                "attention"
                if (licenses.get("counts") or {}).get("pending")
                or (licenses.get("counts") or {}).get("suspended")
                else "ok"
            ),
            "observe_only": True,
        },
        "broker_fleet": {
            "count": brokers.get("count") or 0,
            "connected": brokers.get("connected") or 0,
            "rows": (brokers.get("connections") or [])[:12],
            "credentials_exposed": False,
            "observe_only": True,
        },
        "support": {
            "pending": support.get("pending_count") or 0,
            "total": support.get("count") or 0,
            "observe_only": True,
        },
        "enterprise_analytics": {
            "active_customers": analytics.get("active_customers"),
            "active_robots": analytics.get("active_robots"),
            "connected_brokers": analytics.get("connected_brokers"),
            "countries_count": analytics.get("countries_count"),
            "revenue": analytics.get("revenue"),
            "support_pending": (analytics.get("support_metrics") or {}).get("pending"),
            "license_metrics": analytics.get("license_metrics"),
            "fabricated": False,
            "observe_only": True,
        },
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "cop_version": "v1.0.0",
        },
    }


# Re-export workspace builder for router
__all__ = [
    "build_customer_operations_platform",
    "build_customer_ops_noc_panels",
    "build_customer_workspace",
]
