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

router = APIRouter(prefix="/broker-connectivity", tags=["broker-connectivity"])


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
    try:
        from app.presentation.dependencies.weltrade import get_weltrade_service

        profile = get_weltrade_service().profile()
        servers = profile.get("servers") if isinstance(profile, dict) else None
        if isinstance(servers, dict):
            names: list[str] = []
            for key in ("live", "demo"):
                block = servers.get(key)
                if isinstance(block, list):
                    names.extend(str(item) for item in block if item)
            if names:
                discovered["weltrade"] = names
    except Exception:
        # Profile unavailable — registry still returns verified Weltrade rows.
        pass
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
    discovered: list[str] = []
    if slug == "weltrade":
        try:
            from app.presentation.dependencies.weltrade import get_weltrade_service

            profile = get_weltrade_service().profile()
            servers = profile.get("servers") if isinstance(profile, dict) else None
            if isinstance(servers, dict):
                for key in ("live", "demo"):
                    block = servers.get(key)
                    if isinstance(block, list):
                        discovered.extend(str(item) for item in block if item)
        except Exception:
            pass
    rows = verified_servers_for_broker(slug, discovered=discovered)
    return {
        "broker": slug,
        "connection_status": (
            meta["connection_status"] if meta else "not_verified"
        ),
        "connectable": bool(meta["connectable"]) if meta else False,
        "servers": rows,
        # Documented search hints are admin diagnostics only — not connect options.
        "documented_search_hints": documented_hints_for_admin(slug),
    }


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
