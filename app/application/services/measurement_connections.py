"""Search Console and GA4 connection status. No metric is invented."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def _present(env: Mapping[str, str], name: str) -> bool:
    return bool(str(env.get(name) or "").strip())


def measurement_status(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Report whether a sync could run. Tokens are not copied into the result."""
    env = os.environ if environ is None else environ
    oauth = all(
        _present(env, name)
        for name in (
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REFRESH_TOKEN",
        )
    )
    search_ready = oauth and _present(env, "GOOGLE_SEARCH_CONSOLE_SITE_URL")
    ga4_ready = oauth and _present(env, "GA4_PROPERTY_ID")
    return {
        "search_console": (
            "authorized_sync_not_run" if search_ready else "not_connected"
        ),
        "ga4": "authorized_sync_not_run" if ga4_ready else "not_connected",
        "values": {
            "search_impressions": None,
            "subscribers": None,
            "revenue": None,
            "churn": None,
            "activation": None,
        },
        "places_orders": False,
        "exposes_tokens": False,
    }
