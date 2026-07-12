"""Session context middleware — attaches auth session metadata to the request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SessionMiddleware(BaseHTTPMiddleware):
    """Initialize per-request session slots used by auth dependencies.

    Complements :class:`AuthenticationMiddleware` by ensuring session-related
    request state keys always exist (safe defaults for anonymous traffic).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not hasattr(request.state, "access_token"):
            request.state.access_token = None
        if not hasattr(request.state, "authenticated"):
            request.state.authenticated = False
        if not hasattr(request.state, "current_user_id"):
            request.state.current_user_id = None
        response = await call_next(request)
        return response
