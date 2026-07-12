"""Bearer token extraction middleware (authentication context)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Extract ``Authorization: Bearer`` into ``request.state.access_token``.

    Does not reject unauthenticated requests — route dependencies enforce
    authentication where required.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        authorization = request.headers.get("authorization", "")
        token = ""
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        request.state.access_token = token or None
        request.state.authenticated = bool(token)
        return await call_next(request)
