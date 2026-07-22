"""Optional WebSocket stream — heartbeat / status pulses."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.token_util import (
    mask_gateway_token,
    normalize_gateway_token,
    tokens_equal,
)

logger = logging.getLogger("quantforg.mt5_gateway.auth")

ws_router = APIRouter(tags=["mt5-gateway-ws"])


@ws_router.websocket("/ws")
async def gateway_ws(websocket: WebSocket) -> None:
    settings = get_gateway_settings()
    if not settings.mt5_gateway_enable_websocket:
        await websocket.close(code=1008)
        return

    # Prefer headers over query-string tokens (query tokens leak into proxies/logs).
    raw = websocket.headers.get("x-gateway-token", "")
    if not raw:
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            raw = auth[7:]
    if not raw:
        query_tok = websocket.query_params.get("token") or ""
        if query_tok:
            if not settings.mt5_gateway_allow_query_token:
                logger.warning(
                    "gateway_ws_query_token_rejected — set "
                    "MT5_GATEWAY_ALLOW_QUERY_TOKEN=true only for legacy clients"
                )
                await websocket.close(code=4401)
                return
            logger.warning(
                "gateway_ws_auth_via_query_token — prefer Authorization header"
            )
            raw = query_tok
    token = normalize_gateway_token(raw)
    expected = normalize_gateway_token(settings.mt5_gateway_token)
    equal = tokens_equal(token, expected)
    logger.info(
        "gateway_ws_auth expected=%s received=%s equal=%s",
        mask_gateway_token(expected),
        mask_gateway_token(token),
        equal,
    )
    if not expected or not equal:
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
