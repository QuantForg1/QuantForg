"""MT5 Gateway REST routes — separate process from QuantForg API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from services.mt5_gateway.auth import require_gateway_token
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.schemas import AttachRequest, ConnectRequest
from services.mt5_gateway.settings import get_gateway_settings

router = APIRouter(tags=["mt5-gateway"])


def get_runtime(request: Request) -> MT5GatewayRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway runtime not initialized",
        )
    return runtime  # type: ignore[no-any-return]


RuntimeDep = Annotated[MT5GatewayRuntime, Depends(get_runtime)]
TokenDep = Annotated[str, Depends(require_gateway_token)]


def _call(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Liveness/readiness — optionally open without token."""
    settings = get_gateway_settings()
    runtime = getattr(request.app.state, "runtime", None)
    payload: dict[str, Any] = {
        "status": "ok",
        "service": "mt5-gateway",
        "token_configured": bool(settings.mt5_gateway_token),
        "websocket_enabled": settings.mt5_gateway_enable_websocket,
        "auto_attach_enabled": settings.mt5_gateway_auto_attach,
    }
    if not settings.mt5_gateway_token:
        payload["setup_hint"] = (
            "Set MT5_GATEWAY_TOKEN on this Windows host "
            "(see deploy/mt5_gateway/gateway.env.example), then restart. "
            "After that POST /session/attach or /session/connect."
        )
    if runtime is not None:
        payload["mt5"] = runtime.health()
        payload["bridge_available"] = runtime.bridge.available
    return payload


@router.get("/diagnostics")
async def diagnostics(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return runtime.diagnostics_snapshot()


@router.post("/session/connect")
async def connect(
    body: ConnectRequest, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return _call(
        lambda: runtime.connect(
            login=body.login,
            password=body.password,
            server=body.server,
            path=body.path,
        )
    )


@router.post("/session/attach")
async def attach(
    body: AttachRequest, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    """Reuse an already logged-in MT5 terminal (no broker password)."""
    return _call(lambda: runtime.attach(path=body.path))


@router.post("/session/disconnect")
async def disconnect(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return runtime.disconnect()


@router.get("/session/status")
async def session_status(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return runtime.status()


@router.get("/heartbeat")
async def heartbeat(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return _call(runtime.heartbeat)


@router.get("/account")
async def account(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return _call(runtime.account)


@router.get("/symbols")
async def symbols(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return _call(runtime.symbols)


@router.get("/quotes/{symbol}")
async def quotes(
    symbol: str, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return _call(lambda: runtime.quote(symbol))


@router.get("/candles/{symbol}")
async def candles(
    symbol: str,
    _: TokenDep,
    runtime: RuntimeDep,
    timeframe: str = Query(default="H1"),
    count: int = Query(default=100, ge=1, le=5000),
) -> dict[str, Any]:
    return _call(
        lambda: runtime.candles(symbol, timeframe=timeframe, count=count)
    )


@router.get("/positions")
async def positions(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return _call(runtime.positions)


@router.get("/orders")
async def orders(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return _call(runtime.orders)


@router.get("/history/orders")
async def history_orders(
    _: TokenDep,
    runtime: RuntimeDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return _call(lambda: runtime.history_orders(days=days))


@router.get("/history/deals")
async def history_deals(
    _: TokenDep,
    runtime: RuntimeDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return _call(lambda: runtime.history_deals(days=days))
