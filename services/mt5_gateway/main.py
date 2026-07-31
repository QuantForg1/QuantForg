"""MT5 Gateway ASGI application — Windows host process.

Does not replace QuantForg `/api/v1/mt5`. Credentials stay on this host.

Single-instance protection runs in ``run()`` *before* any ``uvicorn`` import
or ``uvicorn.run()`` call, so a healthy existing gateway never reaches
socket bind / "Application startup complete".
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.mt5_gateway import __version__ as gateway_version
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
        version=gateway_version,
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


# ASGI app object for ``uvicorn services.mt5_gateway.main:app`` (external launcher).
# Direct ``python -m services.mt5_gateway.main`` uses ``run()`` which gates first.
app = create_app()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="services.mt5_gateway.main",
        description="QuantForg MT5 Gateway (single-instance protected)",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help=(
            "Stop any existing gateway on the configured port, wait for socket "
            "release, then start a fresh instance and verify /health."
        ),
    )
    return parser.parse_args(argv)


def _run_uvicorn(*, host: str, port: int) -> None:
    """Import and start uvicorn only after the single-instance gate passes."""
    import uvicorn

    uvicorn.run(
        "services.mt5_gateway.main:app",
        host=host,
        port=port,
        reload=False,
    )


def run(argv: list[str] | None = None) -> None:
    """CLI entrypoint — single-instance gate BEFORE uvicorn bind.

    Validation contract:
    - Healthy existing gateway → print banner, exit 0, never call uvicorn.run
    - Never reach "Application startup complete" / WinError 10048 in that case
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args(argv)

    # Import gate helpers only here (stdlib + settings) — not uvicorn.
    from services.mt5_gateway.single_instance import (
        ensure_single_instance,
        port_can_bind_exclusively,
        read_gateway_bind_settings,
        wait_for_healthy_gateway,
    )

    host, port = read_gateway_bind_settings()

    try:
        action = ensure_single_instance(
            host=host, port=port, restart=bool(args.restart)
        )
    except Exception as exc:
        logger.error("Single-instance gate failed: %s", exc)
        print(f"Gateway startup aborted: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    if action == "already_running":
        # Banner + /health already verified. Do NOT import/start uvicorn.
        raise SystemExit(0)

    # Fail-closed: refuse to start unless exclusive bind is available now.
    if not port_can_bind_exclusively(host, port):
        print(
            f"Gateway startup aborted: port {port} is not exclusively available. "
            "Another process still owns the socket.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1)

    logger.info(
        "Starting QuantForg MT5 Gateway version=%s host=%s port=%s restart=%s",
        gateway_version,
        host,
        port,
        bool(args.restart),
    )

    if args.restart:

        def _announce_restart() -> None:
            snap = wait_for_healthy_gateway(host, port, timeout=30.0)
            if snap.ok:
                print("Gateway restarted successfully", flush=True)
                logger.info(
                    "Gateway restarted successfully version=%s mt5=%s broker=%s",
                    snap.gateway_version,
                    snap.mt5_status,
                    snap.broker,
                )
            else:
                logger.error(
                    "Gateway restarted but /health verify failed: %s", snap.error
                )
                print(
                    f"Gateway restarted but /health verify failed: {snap.error}",
                    file=sys.stderr,
                    flush=True,
                )

        threading.Thread(
            target=_announce_restart, name="qf-gw-restart-verify", daemon=True
        ).start()

    _run_uvicorn(host=host, port=port)


if __name__ == "__main__":
    # Earliest CLI hook for ``py -m services.mt5_gateway.main``.
    run()
