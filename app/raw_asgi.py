"""Raw ASGI application — zero dependencies beyond the ASGI callable.

Used for Railway edge forensics when even FastAPI is suspect.
"""

from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from typing import Any

ROUTES = {
    "/": b'{"status":"ok"}',
    "/health": b'{"ok":true}',
    "/health/live": b'{"status":"alive"}',
    "/health/ready": b'{"status":"ready"}',
}

print(
    "qf_raw_asgi_loaded" f" python={sys.version.split()[0]}" f" module=app.raw_asgi",
    flush=True,
)

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def app(scope: dict[str, Any], receive: Receive, send: Send) -> None:
    _ = receive
    if scope["type"] != "http":
        return

    path = scope.get("path", "/")
    method = scope.get("method", "GET")
    body = ROUTES.get(path)
    status = 200 if body is not None else 404
    if body is None:
        body = b'{"error":"not_found"}'
    if method == "HEAD":
        body = b""

    print(
        f"qf_raw_asgi_request method={method} path={path} status={status}",
        flush=True,
    )

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode("ascii")],
                [b"cache-control", b"no-store"],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
