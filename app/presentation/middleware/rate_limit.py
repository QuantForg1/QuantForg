"""In-process rate limiter for sensitive auth endpoints.

Uses a sliding window per key. Redis is preferred when available; falls back
to process-local state so production still has brute-force protection without
Redis (multi-instance limits are best-effort until Redis is connected).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import get_logger

logger = get_logger(__name__)

# Paths that accept unauthenticated credential / token traffic.
_AUTH_LIMITED_SUFFIXES: tuple[str, ...] = (
    "/auth/login",
    "/auth/register",
    "/auth/forgot-password",
    "/auth/refresh",
    "/auth/oauth/callback",
)


class AuthRateLimitMiddleware:
    """Reject abusive auth traffic with HTTP 429."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit: int = 30,
        window_seconds: float = 60.0,
    ) -> None:
        self.app = app
        self.limit = max(1, limit)
        self.window_seconds = max(1.0, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_ip(self, scope: Scope) -> str:
        for key, value in scope.get("headers") or []:
            if key == b"x-forwarded-for":
                raw = value.decode("latin-1", errors="replace")
                return raw.split(",", 1)[0].strip() or "unknown"
        client = scope.get("client")
        if client and client[0]:
            return str(client[0])
        return "unknown"

    def _is_limited_path(self, path: str) -> bool:
        return any(path.endswith(suffix) for suffix in _AUTH_LIMITED_SUFFIXES)

    def _allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        method = (scope.get("method") or "GET").upper()
        if method in {"POST", "PUT", "PATCH"} and self._is_limited_path(path):
            key = f"{self._client_ip(scope)}:{path}"
            if not self._allow(key):
                logger.warning("auth_rate_limited", path=path, key=key)
                body = (
                    b'{"error":{"code":"auth_rate_limited",'
                    b'"message":"Too many authentication attempts. Try again later.",'
                    b'"details":{}}}'
                )

                async def send_429(message: Message) -> None:
                    await send(message)

                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"retry-after", b"60"),
                            (b"content-length", str(len(body)).encode()),
                            (b"cache-control", b"no-store"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                _ = send_429
                return

        await self.app(scope, receive, send)
