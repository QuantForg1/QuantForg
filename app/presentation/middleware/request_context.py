"""Request context middleware.

Assigns a unique request ID to every inbound HTTP request, binds it into
the structured logging context, and echoes it on the response.
"""

from __future__ import annotations

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

        clear_context()
        bind_context(request_id=request_id)

        timer = Timer()
        timer.__enter__()

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
                timer.__exit__(None, None, None)
                logger.info(
                    "request_completed",
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status=message.get("status"),
                    duration_ms=round(timer.elapsed_ms, 2),
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            clear_context()
