"""MT5 Gateway ASGI application — Windows host process.

Does not replace QuantForg `/api/v1/mt5`. Credentials stay on this host.

Single-instance protection: refuses to bind when a healthy gateway already
owns the listen port (prevents WinError 10048). Use ``--restart`` to recycle.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from services.mt5_gateway import __version__ as gateway_version
from services.mt5_gateway.routers import router
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.single_instance import (
    ensure_single_instance,
    wait_for_healthy_gateway,
)
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


def run(argv: list[str] | None = None) -> None:
    """Entrypoint for ``python -m services.mt5_gateway.main``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args(argv)
    settings = get_gateway_settings()
    host = settings.mt5_gateway_host
    port = int(settings.mt5_gateway_port)

    try:
        action = ensure_single_instance(
            host=host, port=port, restart=bool(args.restart)
        )
    except Exception as exc:
        logger.error("Single-instance gate failed: %s", exc)
        print(f"Gateway startup aborted: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    if action == "already_running":
        # Already printed identity banner + verified /health. Success exit.
        raise SystemExit(0)

    logger.info(
        "Starting QuantForg MT5 Gateway version=%s host=%s port=%s restart=%s",
        gateway_version,
        host,
        port,
        bool(args.restart),
    )

    # When --restart, verify /health in a child-friendly way after bind by
    # running uvicorn programmatically is blocking — operators typically
    # verify externally. For --restart we still start here; a short post-bind
    # note is logged. Full verify for --restart stop/start path that returns
    # after spawning is handled when this process itself becomes the server.
    #
    # If this process is the new instance, success logging after listen is the
    # uvicorn access log; we emit the operator line when restart was requested
    # once the server thread is up via a callback.
    if args.restart:
        # uvicorn.run blocks; use a background poller for the success line.
        import threading

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

    uvicorn.run(
        "services.mt5_gateway.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
