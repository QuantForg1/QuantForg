"""Canonical frontend origins for CORS and auth redirect allowlists.

Keeps custom domains (apex + www), Vercel previews, and local dev aligned
without hardcoding a single deployment URL into the SPA.
"""

from __future__ import annotations

# Exact origins always seeded into production CORS_ALLOWED_ORIGINS.
PRODUCTION_FRONTEND_ORIGINS: tuple[str, ...] = (
    "https://quantforg.com",
    "https://www.quantforg.com",
)

# Starlette CORSMiddleware allow_origin_regex for production.
# Matches:
#   https://*.vercel.app (and nested preview hosts)
#   https://quantforg.com / https://www.quantforg.com / https://*.quantforg.com
PRODUCTION_CORS_ORIGIN_REGEX = (
    r"https://("
    r"([a-zA-Z0-9-]+\.)*vercel\.app"
    r"|"
    r"([a-zA-Z0-9-]+\.)*quantforg\.com"
    r")"
)

LOCAL_DEV_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
)


def is_trusted_frontend_origin(origin: str) -> bool:
    """Return True when *origin* is a known QuantForg frontend host."""
    value = (origin or "").strip().rstrip("/")
    if not value:
        return False
    if value in PRODUCTION_FRONTEND_ORIGINS or value in LOCAL_DEV_ORIGINS:
        return True
    # https://foo.vercel.app or https://quantforg.com / subdomain
    if value.startswith("https://") and (
        value.endswith(".vercel.app")
        or value == "https://vercel.app"
        or value.endswith(".quantforg.com")
        or value == "https://quantforg.com"
    ):
        return True
    if value.startswith("http://localhost:") or value.startswith("http://127.0.0.1:"):
        return True
    return False
