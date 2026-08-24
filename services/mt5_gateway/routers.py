"""MT5 Gateway REST routes — separate process from QuantForg API."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from services.mt5_gateway.auth import require_gateway_token
from services.mt5_gateway.runtime import MT5CallTimeout, MT5GatewayRuntime
from services.mt5_gateway.schemas import (
    AttachRequest,
    CancelRequest,
    ConnectRequest,
    TradeRequestBody,
)
from services.mt5_gateway.settings import get_gateway_settings

router = APIRouter(tags=["mt5-gateway"])

# Dedicated pool so market-data storms cannot starve /health.
_HEALTH_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gw-health")
_MD_SEM: asyncio.Semaphore | None = None


def _market_sem() -> asyncio.Semaphore:
    global _MD_SEM
    if _MD_SEM is None:
        n = int(get_gateway_settings().mt5_max_concurrent_market_requests or 4)
        _MD_SEM = asyncio.Semaphore(max(1, n))
    return _MD_SEM


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
    except MT5CallTimeout as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        # Invalid request fields / symbol trade constraints — never 500.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        # Surface exact failure to callers (Railway OMS) instead of opaque 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc


async def _call_async(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run blocking MT5 bridge work off the event loop (candles/ticks/account)."""
    async with _market_sem():
        return await asyncio.to_thread(_call, fn)


async def _call_trade_async(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Trade path: off the event loop, but not queued behind market-data concurrency."""
    return await asyncio.to_thread(_call, fn)


# In-flight dedupe for identical market-data GETs (scanner fan-out).
_INFLIGHT: dict[str, asyncio.Future[dict[str, Any]]] = {}


async def _deduped_market(
    key: str, fn: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Share one MT5 call across concurrent identical requests."""
    existing = _INFLIGHT.get(key)
    if existing is not None and not existing.done():
        return await asyncio.shield(existing)

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    _INFLIGHT[key] = fut

    async def _run() -> None:
        try:
            result = await _call_async(fn)
            if not fut.done():
                fut.set_result(result)
        except Exception as exc:
            if not fut.done():
                fut.set_exception(exc)
        finally:
            if _INFLIGHT.get(key) is fut:
                _INFLIGHT.pop(key, None)

    asyncio.create_task(_run())
    return await asyncio.shield(fut)


@router.get("/health/live")
async def health_live() -> dict[str, Any]:
    """Process liveness only — never touches MetaTrader5 or the ops lock."""
    from services.mt5_gateway import __version__ as gateway_version

    return {
        "status": "ok",
        "service": "mt5-gateway",
        "gateway_version": gateway_version,
        "probe": "live",
    }


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Liveness/readiness — open without token (auth intentionally bypassed).

    Never blocks the event loop on MetaTrader5. MT5 probes run in a dedicated
    health thread pool with a hard timeout; degraded MT5 still returns HTTP 200.
    """
    from services.mt5_gateway.settings import token_load_meta
    from services.mt5_gateway.token_util import (
        mask_gateway_token,
        normalize_gateway_token,
    )

    settings = get_gateway_settings()
    runtime = getattr(request.app.state, "runtime", None)
    token = normalize_gateway_token(settings.mt5_gateway_token)
    meta = token_load_meta()
    from services.mt5_gateway import __version__ as gateway_version

    payload: dict[str, Any] = {
        "status": "ok",
        "service": "mt5-gateway",
        "gateway_version": gateway_version,
        "token_configured": bool(token) and len(token) > 0,
        "websocket_enabled": settings.mt5_gateway_enable_websocket,
        "auto_attach_enabled": settings.mt5_gateway_auto_attach,
        "token_fingerprint": {
            "length": len(token),
            "preview": mask_gateway_token(token),
            "source": getattr(settings, "token_source", meta.get("source")),
            "process_env_len": meta.get("process_env_len"),
            "dotenv_len": meta.get("dotenv_len"),
            "dotenv_path": meta.get("dotenv_path"),
            "process_is_placeholder": meta.get("process_is_placeholder"),
        },
    }
    if not token:
        payload["setup_hint"] = (
            "Set MT5_GATEWAY_TOKEN on this Windows host "
            "(see deploy/mt5_gateway/gateway.env.example), then restart. "
            "After that POST /session/attach or /session/connect."
        )
    if runtime is not None:
        # Hard ceiling so /health never exceeds ~500ms even if probe settings drift.
        ceiling = min(0.45, float(settings.mt5_health_probe_timeout_seconds) + 0.1)
        loop = asyncio.get_running_loop()
        try:
            mt5_payload = await asyncio.wait_for(
                loop.run_in_executor(_HEALTH_POOL, runtime.health),
                timeout=ceiling,
            )
        except TimeoutError:
            from services.mt5_gateway.runtime import _empty_capability_fields

            snap = runtime.try_lock_snapshot(wait_seconds=0.0)
            mt5_payload = {
                "connected": bool(snap.get("connected")),
                "session_mode": snap.get("session_mode") or "none",
                "latency_ms": None,
                "terminal_build": None,
                "build_date": None,
                "server": getattr(getattr(runtime, "diagnostics", None), "server", None)
                or None,
                "login_status": "timeout",
                "last_heartbeat_at": snap.get("last_heartbeat_at"),
                "version": "",
                "bridge_available": bool(snap.get("bridge_available")),
                "degraded": True,
                "probe": "async_ceiling",
                "ops_lock": snap.get("lock"),
                **_empty_capability_fields(
                    reason="health probe timed out — terminal capabilities not read"
                ),
            }
        payload["mt5"] = mt5_payload
        payload["bridge_available"] = runtime.bridge.available
        # When the MetaTrader5 Python package failed to import, expose the
        # import error on public /health so operators can diagnose without a
        # token (attach/diagnostics remain authenticated).
        if not runtime.bridge.available:
            payload["bridge_import_error"] = runtime.bridge._import_error
            mt5_payload["bridge_import_error"] = runtime.bridge._import_error
            # Interpreter mismatch evidence (sys.executable vs pip target).
            import_ctx = getattr(runtime.bridge, "_import_context", None)
            if isinstance(import_ctx, dict):
                payload["bridge_import_context"] = import_ctx
                mt5_payload["bridge_import_context"] = import_ctx
        else:
            # Surface last initialize attempt when import works but session is down.
            init_err = getattr(runtime.bridge, "_last_initialize_error", None)
            init_ok = getattr(runtime.bridge, "_last_initialize_ok", None)
            if init_ok is False or (
                not mt5_payload.get("connected") and init_err is not None
            ):
                payload["bridge_initialize_ok"] = init_ok
                payload["bridge_initialize_error"] = init_err
                mt5_payload["bridge_initialize_ok"] = init_ok
                mt5_payload["bridge_initialize_error"] = init_err
        # Top-level status stays "ok" while the gateway process is serving —
        # MT5 degradation lives under payload["mt5"] so live probes still see
        # a reachable gateway (HTTP 200 + status=ok).
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
    return await _call_async(runtime.heartbeat)


@router.get("/account")
async def account(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return await _deduped_market("account", runtime.account)


@router.get("/symbols")
async def symbols(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return await _deduped_market("symbols", runtime.symbols)


@router.get("/symbols/{symbol}")
async def symbol_specs(symbol: str, _: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    """Live MT5 constraints: volume_step, stops_level, filling_mode, trade_mode, …"""
    key = f"symbol_specs:{symbol.strip().upper()}"
    return await _deduped_market(key, lambda: runtime.symbol_specs(symbol))


@router.get("/quotes/{symbol}")
async def quotes(symbol: str, _: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    key = f"quote:{symbol.strip().upper()}"
    return await _deduped_market(key, lambda: runtime.quote(symbol))


@router.get("/candles/{symbol}")
async def candles(
    symbol: str,
    _: TokenDep,
    runtime: RuntimeDep,
    timeframe: str = Query(default="H1"),
    count: int = Query(default=100, ge=1, le=5000),
) -> dict[str, Any]:
    key = f"candles:{symbol.strip().upper()}:{timeframe.strip().upper()}:{count}"
    return await _deduped_market(
        key, lambda: runtime.candles(symbol, timeframe=timeframe, count=count)
    )


@router.get("/positions")
async def positions(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return await _deduped_market("positions", runtime.positions)


@router.get("/orders")
async def orders(_: TokenDep, runtime: RuntimeDep) -> dict[str, Any]:
    return await _deduped_market("orders", runtime.orders)


@router.get("/history/orders")
async def history_orders(
    _: TokenDep,
    runtime: RuntimeDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return await _call_async(lambda: runtime.history_orders(days=days))


@router.get("/history/deals")
async def history_deals(
    _: TokenDep,
    runtime: RuntimeDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return await _deduped_market(
        f"history_deals:{days}", lambda: runtime.history_deals(days=days)
    )


@router.post("/trade/order_check")
async def trade_order_check(
    body: TradeRequestBody, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return await _call_trade_async(lambda: runtime.order_check(body.as_runtime_dict()))


@router.post("/trade/order_calc_margin")
async def trade_order_calc_margin(
    body: TradeRequestBody, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return await _call_trade_async(
        lambda: runtime.order_calc_margin(body.as_runtime_dict())
    )


@router.post("/trade/order_calc_profit")
async def trade_order_calc_profit(
    body: TradeRequestBody, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return await _call_trade_async(
        lambda: runtime.order_calc_profit(body.as_runtime_dict())
    )


@router.post("/trade/order_send")
async def trade_order_send(
    body: TradeRequestBody, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    """Live MetaTrader5.order_send — never invents tickets."""
    return await _call_trade_async(lambda: runtime.order_send(body.as_runtime_dict()))


@router.post("/trade/order_cancel")
async def trade_order_cancel(
    body: CancelRequest, _: TokenDep, runtime: RuntimeDep
) -> dict[str, Any]:
    return await _call_trade_async(lambda: runtime.order_cancel(body.ticket))