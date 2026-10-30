"""Router registration boot state for readiness and diagnostics.

Tracks which FastAPI routers from ``_ROUTER_SPECS`` have been mounted,
which failed, and whether deferred registration has finished. Never
includes secrets or stack traces in public payloads.
"""

from __future__ import annotations

from typing import Any

# Must be registered (or still pending) before readiness reports ok.
# Optional institutional / research routers may fail without failing readiness.
CRITICAL_READY_ROUTERS: frozenset[str] = frozenset(
    {
        "health",
        "version",
        "auth",
        "brokers",
        "mt5",
        "trading_session",
        "execution",
        "portfolio",
        "risk",
    }
)


def empty_router_boot(
    *,
    mode: str,
    pending: tuple[tuple[str, str], ...] = (),
    registered: list[str] | None = None,
) -> dict[str, Any]:
    """Initial boot snapshot attached to ``app.state.router_boot``."""
    pending_names = [name for name, _ in pending]
    return {
        "status": "pending" if pending_names else "complete",
        "mode": mode,  # eager | deferred
        "registered": list(registered or []),
        "failed": [],
        "pending": pending_names,
        "critical_failed": [],
        "first_failure": None,
    }


def merge_registration_summary(
    boot: dict[str, Any],
    summary: dict[str, Any],
    *,
    remaining_pending: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    """Merge a ``_register_routers`` summary into boot state."""
    registered = list(boot.get("registered") or [])
    for name in summary.get("registered") or []:
        if name not in registered:
            registered.append(name)
    failed = list(boot.get("failed") or [])
    for name in summary.get("failed") or []:
        if name not in failed:
            failed.append(name)
    pending_names = [name for name, _ in remaining_pending]
    critical_failed = sorted(name for name in failed if name in CRITICAL_READY_ROUTERS)
    if pending_names:
        status = "pending"
    elif critical_failed:
        status = "not_ready"
    elif failed:
        status = "degraded"
    else:
        status = "complete"
    return {
        "status": status,
        "mode": boot.get("mode") or "deferred",
        "registered": registered,
        "failed": failed,
        "pending": pending_names,
        "critical_failed": critical_failed,
        "first_failure": summary.get("first_failure") or boot.get("first_failure"),
        "route_registration_ms": summary.get("route_registration_ms"),
    }


def evaluate_readiness(boot: dict[str, Any] | None) -> dict[str, Any]:
    """Public readiness view derived from router boot state.

    Returns keys: status, http_ready, detail, routers (safe subset).
    """
    if boot is None:
        return {
            "status": "ok",
            "http_ready": True,
            "detail": "router_boot_untracked",
            "routers": {"status": "unknown"},
        }
    status = str(boot.get("status") or "unknown")
    pending = list(boot.get("pending") or [])
    critical_failed = list(boot.get("critical_failed") or [])
    failed = list(boot.get("failed") or [])
    registered_count = len(boot.get("registered") or [])

    routers = {
        "status": status,
        "registered_count": registered_count,
        "pending_count": len(pending),
        "failed_count": len(failed),
        "critical_failed": critical_failed,
        # Names only — never modules/paths that might leak layout.
        "failed": failed[:40],
    }

    if status == "pending" or pending:
        return {
            "status": "initializing",
            "http_ready": False,
            "detail": "deferred_routers_pending",
            "routers": routers,
        }
    if critical_failed or status == "not_ready":
        return {
            "status": "not_ready",
            "http_ready": False,
            "detail": "critical_router_registration_failed",
            "routers": routers,
        }
    if failed or status == "degraded":
        return {
            "status": "degraded",
            "http_ready": True,
            "detail": "optional_router_registration_failed",
            "routers": routers,
        }
    return {
        "status": "ok",
        "http_ready": True,
        "detail": "routers_registered",
        "routers": routers,
    }
