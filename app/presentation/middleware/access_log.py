"""Temporary/diagnostic access log for every HTTP request.

Logs METHOD, PATH, and STATUS so Railway proxy failures are visible in deploy logs.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import get_logger

logger = get_logger(__name__)


class RequestAccessLogMiddleware:
    """Outermost middleware — log every request that reaches the ASGI app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        host = b""
        for key, value in scope.get("headers") or []:
            if key == b"host":
                host = value
                break
        host_str = host.decode("latin-1", errors="replace")
        status_box: dict[str, int | None] = {"code": None}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_box["code"] = int(message.get("status", 0))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception(
                "incoming_request_exception",
                method=method,
                path=path,
                host=host_str,
            )
            raise
        finally:
            logger.info(
                "incoming_request",
                method=method,
                path=path,
                status_code=status_box["code"],
                host=host_str,
            )
