"""Request context middleware.

Assigns a unique request ID to every inbound HTTP request, binds it into
the structured logging context, and echoes it on the response.
"""

from __future__ import annotations

from contextlib import suppress

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import bind_context, clear_context, get_logger
from core.utils.identifiers import new_request_id
from core.utils.timing import Timer

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware:
    """ASGI middleware for request correlation and timing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)
        request_id = headers.get(REQUEST_ID_HEADER.lower()) or new_request_id()
        state = scope.setdefault("state", {})
        with suppress(Exception):
            state["request_id"] = request_id  # type: ignore[index]

        clear_context()
        bind_context(request_id=request_id)

        timer = Timer()
        timer.__enter__()
        status_code_box: dict[str, int | None] = {"code": None}

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
                status_code_box["code"] = int(message.get("status", 0) or 0)
                timer.__exit__(None, None, None)
                duration_ms = round(timer.elapsed_ms, 2)
                logger.info(
                    "request_completed",
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status=status_code_box["code"],
                    duration_ms=duration_ms,
                )
                # Best-effort metrics (container may not be ready yet).
                with suppress(Exception):
                    from core.di.container import get_container

                    collector = getattr(get_container(), "metrics_collector", None)
                    if collector is not None:
                        code = status_code_box["code"] or 500
                        collector.record_request(
                            latency_ms=duration_ms,
                            success=code < 500,
                        )
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            clear_context()
