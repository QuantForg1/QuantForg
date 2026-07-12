"""Bare ASGI app for Railway outage isolation.

No middleware, no lifespan, no DI, no settings. Used when QF_MINIMAL=1
(or as a forensic fallback) to prove the edge can reach a FastAPI response.
"""

from __future__ import annotations

import sys

from fastapi import FastAPI

app = FastAPI(title="QuantForg-Minimal", docs_url=None, redoc_url=None)

print(
    "qf_asgi_forensics"
    f" type={type(app)!r}"
    f" id={id(app)}"
    f" module={type(app).__module__}"
    f" repr={app!r}"
    f" python={sys.version.split()[0]}",
    flush=True,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
