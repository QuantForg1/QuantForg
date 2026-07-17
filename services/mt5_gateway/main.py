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


def _log_loaded_auth_module() -> None:
    """TEMPORARY: prove which auth.py is imported at runtime (remove after diagnosis)."""
    import inspect
    from pathlib import Path

    import services.mt5_gateway.auth as auth_mod
    import services.mt5_gateway.routers as routers_mod

    auth_path = Path(inspect.getfile(auth_mod)).resolve()
    routers_path = Path(inspect.getfile(routers_mod)).resolve()
    require_src = inspect.getsource(auth_mod.require_gateway_token)
    file_text = auth_path.read_text(encoding="utf-8")
    has_helper = hasattr(auth_mod, "_temporary_token_diff_debug")
    helper_called = "_temporary_token_diff_debug(" in require_src
    marker_in_file = "TEMPORARY_GATEWAY_TOKEN_DIFF" in file_text
    equal_after_debug = (
        "_temporary_token_diff_debug(" in require_src
        and "tokens_equal(" in require_src
        and require_src.index("_temporary_token_diff_debug(")
        < require_src.index("tokens_equal(")
    )
    lines = [
        "TEMPORARY_AUTH_MODULE_PROBE",
        f"auth_module={auth_mod.__name__}",
        f"auth_file={auth_path}",
        f"routers_file={routers_path}",
        f"require_gateway_token={auth_mod.require_gateway_token.__qualname__}",
        f"TokenDep_depends={getattr(routers_mod, 'TokenDep', None)}",
        f"has__temporary_token_diff_debug={has_helper}",
        f"marker_TEMPORARY_GATEWAY_TOKEN_DIFF_in_file={marker_in_file}",
        f"helper_called_in_require_gateway_token={helper_called}",
        f"helper_appears_before_tokens_equal={equal_after_debug}",
    ]
    message = "\n".join(lines)
    print(message, flush=True)
    logger.warning(message)
    if not (has_helper and helper_called and equal_after_debug and marker_in_file):
        logger.error(
            "TEMPORARY diagnostics missing from loaded auth.py — "
            "this process is not running the diagnostic build. "
            "auth_file=%s",
            auth_path,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Always reload settings at process start so Windows .env / NSSM env
    # changes apply after restart (clears lru_cache from import-time).
    get_gateway_settings.cache_clear()
    settings = get_gateway_settings()
    from services.mt5_gateway.token_util import mask_gateway_token

    # TEMPORARY — remove after auth diagnosis.
    _log_loaded_auth_module()

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
