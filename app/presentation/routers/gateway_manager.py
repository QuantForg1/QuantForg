"""Gateway Manager API — additive cloud control plane.

Does not modify /mt5, MT5 Gateway routes, auth, or intelligence APIs.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.gateway_manager import GatewayManagerDep
from app.presentation.schemas.gateway_manager import (
    GatewayHeartbeatRequest,
    RegisterGatewayRequest,
    ReplaceGatewayRequest,
    RouteGatewayRequest,
)

router = APIRouter(prefix="/gateway-manager", tags=["gateway-manager"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


@router.get("/dashboard")
async def cloud_dashboard(
    _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    return svc.dashboard()


@router.get("/gateways")
async def list_gateways(
    _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    return svc.list_gateways()


@router.get("/gateways/{gateway_id}")
async def get_gateway(
    gateway_id: str, _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    row = svc.get_gateway(gateway_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return row


@router.post("/gateways")
async def register_gateway(
    body: RegisterGatewayRequest,
    _user: CurrentUser,
    svc: GatewayManagerDep,
) -> dict[str, Any]:
    return svc.register(
        hostname=body.hostname,
        broker=body.broker,
        region=body.region,
        version=body.version,
        base_url=body.base_url,
        capabilities=body.capabilities,
        ip_allowlist=body.ip_allowlist,
        gateway_id=body.gateway_id,
    )


@router.delete("/gateways/{gateway_id}")
async def deregister_gateway(
    gateway_id: str, _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    ok = svc.deregister(gateway_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return {"ok": True, "gateway_id": gateway_id}


@router.post("/gateways/{gateway_id}/rotate-token")
async def rotate_gateway_token(
    gateway_id: str, _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    out = svc.rotate_token(gateway_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return out


@router.post("/gateways/{gateway_id}/replace")
async def replace_gateway(
    gateway_id: str,
    body: ReplaceGatewayRequest,
    _user: CurrentUser,
    svc: GatewayManagerDep,
) -> dict[str, Any]:
    out = svc.replace_gateway(
        old_gateway_id=gateway_id,
        hostname=body.hostname,
        broker=body.broker,
        region=body.region,
        version=body.version,
        base_url=body.base_url,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return out


@router.post("/route")
async def route_user_gateway(
    body: RouteGatewayRequest,
    _user: CurrentUser,
    svc: GatewayManagerDep,
) -> dict[str, Any]:
    return svc.route(
        broker=body.broker, region=body.region, capability=body.capability
    )


@router.post("/ha/refresh")
async def refresh_ha(
    _user: CurrentUser, svc: GatewayManagerDep
) -> dict[str, Any]:
    return svc.refresh_ha()


@router.post("/agents/heartbeat")
async def agent_heartbeat(
    body: GatewayHeartbeatRequest,
    request: Request,
    svc: GatewayManagerDep,
) -> dict[str, Any]:
    """Mutual auth heartbeat from Windows gateway agents (no user JWT)."""
    result = svc.ingest_heartbeat(
        gateway_id=body.gateway_id,
        token=body.token,
        client_ip=_client_ip(request),
        nonce=body.nonce,
        latency_ms=body.latency_ms,
        metrics=body.metrics,
        status=body.status,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=result.get("error", "denied"))
    return result
