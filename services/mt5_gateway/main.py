"""MT5 Gateway ASGI application — Windows host process.

Does not replace QuantForg `/api/v1/mt5`. Credentials stay on this host.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from services.mt5_gateway.routers import router
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.websocket import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = MT5GatewayRuntime()
    runtime.start_background()
    app.state.runtime = runtime
    try:
        yield
    finally:
        runtime.stop_background()
        runtime.disconnect()


def create_app() -> FastAPI:
    settings = get_gateway_settings()
    app = FastAPI(
        title="QuantForg MT5 Gateway",
        version="1.0.0",
        description=(
            "Windows MetaTrader 5 runtime gateway. "
            "Broker credentials stay in gateway memory — not Railway."
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
