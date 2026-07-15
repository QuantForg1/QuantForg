"""MT5 Gateway ASGI application — Windows host process.

Does not replace QuantForg `/api/v1/mt5`. Credentials stay on this host.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from services.mt5_gateway.routers import router
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.websocket import ws_router

logger = logging.getLogger("quantforg.mt5_gateway")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Always reload settings at process start so Windows .env / NSSM env
    # changes apply after restart (clears lru_cache from import-time).
    get_gateway_settings.cache_clear()
    settings = get_gateway_settings()
    from services.mt5_gateway.token_util import mask_gateway_token

    token = (settings.mt5_gateway_token or "").strip()
    if not token:
        logger.warning(
            "MT5_GATEWAY_TOKEN is not set. Protected routes return 503 until "
            "you set a strong token in the Windows host .env "
            "(see deploy/mt5_gateway/gateway.env.example). "
            "Never put broker passwords in Railway."
        )
    else:
        logger.info(
            "MT5_GATEWAY_TOKEN ready source=%s length=%s fingerprint=%s repr=%r",
            getattr(settings, "token_source", "unknown"),
            len(token),
            mask_gateway_token(token),
            token if settings.mt5_gateway_auth_debug else mask_gateway_token(token),
        )

    runtime = MT5GatewayRuntime(settings=settings)
    runtime.start_background()
    app.state.runtime = runtime

    if settings.mt5_gateway_auto_attach:
        try:
            result = runtime.attach(path=settings.mt5_terminal_path)
            logger.info(
                "Auto-attached to MT5 terminal session login=%s server=%s",
                result.get("login"),
                result.get("server"),
            )
        except Exception as exc:
            logger.warning(
                "MT5_GATEWAY_AUTO_ATTACH enabled but attach failed: %s. "
                "Log into the MetaTrader UI, then POST /session/attach or "
                "/session/connect.",
                exc,
            )

    try:
        yield
    finally:
        runtime.stop_background()
        runtime.disconnect()


def create_app() -> FastAPI:
    settings = get_gateway_settings()
    app = FastAPI(
        title="QuantForg MT5 Gateway",
        version="1.1.0",
        description=(
            "Windows MetaTrader 5 runtime gateway. "
            "Broker credentials stay in gateway memory — not Railway. "
            "Use POST /session/attach to reuse an already logged-in terminal, "
            "or POST /session/connect with login/password/server."
        ),
        lifespan=lifespan,
    )
    app.include_router(router)
    if settings.mt5_gateway_enable_websocket:
        app.include_router(ws_router)
    return app


app = create_app()


def run() -> None:
    settings = get_gateway_settings()
    uvicorn.run(
        "services.mt5_gateway.main:app",
        host=settings.mt5_gateway_host,
        port=settings.mt5_gateway_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
