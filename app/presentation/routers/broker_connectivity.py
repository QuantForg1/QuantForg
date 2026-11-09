"""Broker Connectivity Framework API — adapter registry, matrix, diagnostics.

Additive. Does not replace /mt5, /brokers, or Execution Gateway.
Never invents venue connectivity. Never flips EXECUTION_ENABLED.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.broker_connectivity import BrokerConnectivityDep
from app.presentation.schemas.broker_connectivity import (
    ConnectivityTradingRequest,
    InvokeConnectivityRequest,
    RunCertificationRequest,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/broker-connectivity", tags=["broker-connectivity"])


def _weltrade_profile_server_names() -> list[str]:
    """Best-effort Weltrade profile servers — empty when the service is unavailable."""
    try:
        from app.presentation.dependencies.weltrade import get_weltrade_service

        profile = get_weltrade_service().profile()
    except Exception as exc:
        logger.info(
            "mt5_registry_weltrade_profile_unavailable",
            error_type=type(exc).__name__,
        )
        return []
    servers = profile.get("servers") if isinstance(profile, dict) else None
    if not isinstance(servers, dict):
        return []
    names: list[str] = []
    for key in ("live", "demo"):
        block = servers.get(key)
        if isinstance(block, list):
            names.extend(str(item) for item in block if item)
    return names


@router.get("/dashboard")
async def connectivity_dashboard(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Catalog + capability matrix + diagnostics snapshot."""
    return svc.dashboard()


@router.get("/catalog")
async def connectivity_catalog(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    return {"items": svc.catalog()}


@router.get("/matrix")
async def connectivity_matrix(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Broker Capability Matrix (order types, margin, streaming, …)."""
    return {"items": svc.capability_matrix()}


@router.get("/diagnostics")
async def connectivity_diagnostics(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
    platform: str | None = Query(default=None),
) -> dict[str, Any]:
    """Latency, heartbeat, reconnect, failures, capability checks."""
    return svc.diagnostics(platform)


@router.get("/ecosystem")
async def mt5_ecosystem(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """MT5 Broker Ecosystem v1.1 — Weltrade, XM, Exness, IC Markets, Pepperstone."""
    return svc.ecosystem()


@router.get("/mt5-broker-registry")
async def mt5_broker_registry(_user: CurrentUser) -> dict[str, Any]:
    """Honest multi-broker registry — connectable only when production-verified."""
    from app.domain.broker_connectivity.mt5_server_catalogue import catalogue_snapshot

    discovered: dict[str, list[str]] = {}
    names = _weltrade_profile_server_names()
    if names:
        discovered["weltrade"] = names
    return catalogue_snapshot(discovered_by_broker=discovered)


@router.get("/mt5-servers")
async def mt5_servers(
    _user: CurrentUser,
    broker: str = Query(..., min_length=1, description="Broker slug, e.g. weltrade"),
) -> dict[str, Any]:
    """Verified / discovered MT5 servers for one broker — never invents names."""
    from app.domain.broker_connectivity.mt5_server_catalogue import (
        broker_registry_rows,
        documented_hints_for_admin,
        verified_servers_for_broker,
    )

    slug = broker.strip().lower()
    meta = next((row for row in broker_registry_rows() if row["slug"] == slug), None)
    discovered = _weltrade_profile_server_names() if slug == "weltrade" else []
    rows = verified_servers_for_broker(slug, discovered=discovered)
    demo = [r for r in rows if r.get("environment") == "demo"]
    live = [r for r in rows if r.get("environment") == "live"]
    return {
        "broker": slug,
        "connection_status": (meta["connection_status"] if meta else "not_verified"),
        "connectable": bool(meta["connectable"]) if meta else False,
        "servers": rows,
        "servers_by_environment": {"demo": demo, "live": live},
        # Documented search hints are diagnostics only — not verified connect options.
        "documented_search_hints": documented_hints_for_admin(slug),
        "credentials_exposed": False,
        "note": (
            "Selectable connect servers are verified rows only. "
            "Documented hints are search aids and never invent connectivity."
        ),
    }


@router.get("/mt5-worker-ops")
async def mt5_worker_ops(_user: CurrentUser) -> dict[str, Any]:
    """Admin visibility for Windows workers + verification evidence (no passwords)."""
    from app.domain.broker_connectivity.broker_verification_evidence import (
        ops_snapshot,
    )
    from app.domain.broker_connectivity.mt5_server_catalogue import catalogue_snapshot
    from app.domain.broker_connectivity.verification_matrix import (
        build_verification_matrix,
    )
    from app.domain.multi_account.feature_gates import multi_account_live_submit_allowed

    verification = ops_snapshot()
    registry = catalogue_snapshot()
    workers: list[dict[str, Any]] = []
    hosts: dict[str, Any] = {}
    try:
        from app.infrastructure.persistence import (
            postgres_mt5_worker_control_plane as cp_store,
        )

        rows = cp_store.load_all_workers() if cp_store.table_ready() else []
        for row in rows:
            workers.append(
                {
                    "worker_id": row.get("worker_id"),
                    "host_code": row.get("host_code"),
                    "slot_id": row.get("slot_id"),
                    "lifecycle": row.get("lifecycle_status"),
                    "last_heartbeat_at": row.get("last_heartbeat_at"),
                    "last_error": row.get("last_error") or "",
                    "trade_allowed": row.get("trade_allowed"),
                    "account_login_verified": row.get("account_login_verified") or "",
                    "server_verified": row.get("server_verified") or "",
                    "revoked": bool(row.get("revoked")),
                    "credentials_exposed": False,
                }
            )
    except Exception as exc:
        logger.info(
            "mt5_worker_ops_durable_unavailable",
            error_type=type(exc).__name__,
        )
    return {
        "ok": True,
        "credentials_exposed": False,
        "live_submit_enabled": multi_account_live_submit_allowed(),
        "workers": workers,
        "worker_count": len(workers),
        "hosts": hosts,
        "verification": verification,
        "verification_matrix": build_verification_matrix(),
        "registry": registry,
        "gateway": registry.get("gateway"),
        "note": (
            "Passwords are never returned. Brokers remain connectable=false until "
            "a Windows MT5 demo verify writes evidence."
        ),
    }


@router.get("/mt5-verification-matrix")
async def mt5_verification_matrix(_user: CurrentUser) -> dict[str, Any]:
    """Six-broker Demo/Live matrix — PASS only after real Windows MT5 verify."""
    from app.domain.broker_connectivity.verification_matrix import (
        build_verification_matrix,
    )

    return {"ok": True, **build_verification_matrix()}


@router.get("/compatibility")
async def broker_compatibility(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
    broker: str | None = Query(default=None),
    symbol: str = Query(default="EURUSD"),
) -> dict[str, Any]:
    """Live compatibility suite — never invents market/account data."""
    return svc.compatibility(broker_slug=broker, quote_symbol=symbol)


@router.get("/compatibility/dashboard")
async def broker_compatibility_dashboard(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Broker Compatibility Dashboard payload."""
    return svc.compatibility_dashboard()


@router.get("/onboarding/{slug}")
async def broker_onboarding(
    slug: str,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    guide = svc.onboarding(slug)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Unknown broker '{slug}'")
    return guide


@router.get("/certification")
async def certification_status(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
    broker: str | None = Query(default=None),
) -> dict[str, Any]:
    """Current certification status (Not Tested until a real run)."""
    return svc.certification_status(broker)


@router.get("/certification/dashboard")
async def certification_dashboard_route(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Broker Certification Dashboard — certified / pending / failed."""
    return svc.certification_dashboard()


@router.get("/certification/history")
async def certification_history(
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
    broker: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return svc.certification_history(broker_slug=broker, limit=limit)


@router.post("/certification/run")
async def certification_run(
    body: RunCertificationRequest,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Advance certification using the live MT5 session only."""
    return svc.run_certification(
        broker_slug=body.broker,
        quote_symbol=body.symbol,
        tester=body.tester,
    )


@router.get("/{platform}/capabilities")
async def platform_capabilities(
    platform: str,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    if svc.get(platform) is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform '{platform}'")
    return svc.invoke(platform, "capabilities")


@router.get("/{platform}/health")
async def platform_health(
    platform: str,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    if svc.get(platform) is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform '{platform}'")
    return svc.invoke(platform, "health")


@router.get("/{platform}/heartbeat")
async def platform_heartbeat(
    platform: str,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    if svc.get(platform) is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform '{platform}'")
    return svc.invoke(platform, "heartbeat")


@router.post("/invoke")
async def invoke_capability(
    body: InvokeConnectivityRequest,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Invoke a connectivity capability on a registered adapter."""
    if svc.get(body.platform) is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown platform '{body.platform}'"
        )
    return svc.invoke(
        body.platform,
        body.capability,
        params=body.params,
        symbol=body.symbol,
        timeframe=body.timeframe,
        count=body.count,
        limit=body.limit,
        intent=body.intent,
    )


@router.post("/{platform}/trading")
async def platform_trading_probe(
    platform: str,
    body: ConnectivityTradingRequest,
    _user: CurrentUser,
    svc: BrokerConnectivityDep,
) -> dict[str, Any]:
    """Trading capability probe — never order_send; reports EXECUTION_ENABLED gate."""
    if svc.get(platform) is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform '{platform}'")
    return svc.invoke(platform, "trading", intent=body.intent)
