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
)

router = APIRouter(
    prefix="/broker-connectivity", tags=["broker-connectivity"]
)


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
