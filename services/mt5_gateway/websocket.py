"""Optional WebSocket stream — heartbeat / status pulses."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.mt5_gateway.settings import get_gateway_settings

ws_router = APIRouter(tags=["mt5-gateway-ws"])


@ws_router.websocket("/ws")
async def gateway_ws(websocket: WebSocket) -> None:
    settings = get_gateway_settings()
    if not settings.mt5_gateway_enable_websocket:
        await websocket.close(code=1008)
        return

    token = websocket.query_params.get("token") or websocket.headers.get(
        "x-gateway-token", ""
    )
    expected = (settings.mt5_gateway_token or "").strip()
    if not expected or token != expected:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    runtime = getattr(websocket.app.state, "runtime", None)
    try:
        while True:
            payload: dict[str, Any] = {"type": "heartbeat"}
            if runtime is not None:
                try:
                    payload["data"] = runtime.heartbeat()
                except Exception as exc:
                    payload["data"] = {
                        "ok": False,
                        "error": str(exc),
                        "diagnostics": runtime.diagnostics_snapshot(),
                    }
            await websocket.send_json(payload)
            await asyncio.sleep(settings.mt5_heartbeat_interval_seconds)
    except WebSocketDisconnect:
        return
