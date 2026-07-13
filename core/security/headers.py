"""HTTP security headers applied to every response."""

from __future__ import annotations

from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeaders:
    """ASGI middleware that injects standard security response headers.

    Headers applied
    ---------------
    - ``X-Content-Type-Options: nosniff``
    - ``X-Frame-Options: DENY``
    - ``Referrer-Policy: strict-origin-when-cross-origin``
    - ``Permissions-Policy`` (restrictive defaults)
    - ``Cache-Control: no-store`` for API responses
    """

    _HEADERS: Final[dict[str, str]] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store",
    }

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in self._HEADERS.items():
                    headers[key] = value
                # HSTS when the edge terminated TLS (Railway) or direct HTTPS.
                proto = ""
                for hdr_key, hdr_val in scope.get("headers") or []:
                    if hdr_key == b"x-forwarded-proto":
                        proto = hdr_val.decode("latin-1", errors="replace").lower()
                        break
                if proto == "https" or scope.get("scheme") == "https":
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, send_with_headers)
