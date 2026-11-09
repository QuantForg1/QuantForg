"""Verified MT5 broker / server catalogue for Broker Accounts.

Rules
-----
* Only Weltrade is marked ``production_verified`` until another broker's
  MT5 connection is proven on a QuantForg Windows gateway/worker.
* Server rows always carry ``source`` + ``verified_at`` (or null when
  documented-only / not yet discovered).
* Documented ``server_hints`` from the ecosystem profile are NEVER returned
  as verified production servers.
* Live discovery may append servers observed on an attached MT5 terminal
  for the matching broker slug.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.broker_connectivity.mt5_ecosystem import (
    MT5_ECOSYSTEM,
    match_broker_for_server,
    profile_by_slug,
)

# Production-verified Weltrade servers (observed on LIVE gateway accounts).
_WELTRADE_VERIFIED: tuple[dict[str, Any], ...] = (
    {
        "name": "Weltrade-Real",
        "environment": "live",
        "source": "production_gateway_account",
        "verified_at": "2026-11-09T00:00:00+00:00",
    },
    {
        "name": "Weltrade-Demo",
        "environment": "demo",
        "source": "weltrade_profile_defaults",
        "verified_at": "2026-11-09T00:00:00+00:00",
    },
)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def broker_registry_rows() -> list[dict[str, Any]]:
    """UI/admin broker registry — honest verification flags."""
    rows: list[dict[str, Any]] = []
    for profile in sorted(MT5_ECOSYSTEM, key=lambda p: (p.priority, p.slug)):
        verified = profile.slug == "weltrade"
        rows.append(
            {
                "slug": profile.slug,
                "name": profile.name,
                "website": profile.website,
                "platform": "mt5",
                "connection_status": (
                    "production_verified" if verified else "not_verified"
                ),
                "connectable": verified,
                "notes": (
                    "Production Weltrade path via Windows MT5 Gateway."
                    if verified
                    else (
                        "Documented MT5 brand only. Connection is not marked "
                        "operational until a QuantForg Windows gateway/worker "
                        "verifies login for this broker."
                    )
                ),
                "regions": list(profile.regions),
                "priority": profile.priority,
            }
        )
    # Brands requested in product scope but not yet in ecosystem profiles.
    for slug, name, website in (
        ("fp-markets", "FP Markets", "https://www.fpmarkets.com"),
        ("hfm", "HFM", "https://www.hfm.com"),
    ):
        if any(r["slug"] == slug for r in rows):
            continue
        rows.append(
            {
                "slug": slug,
                "name": name,
                "website": website,
                "platform": "mt5",
                "connection_status": "not_verified",
                "connectable": False,
                "notes": (
                    "Documented MT5 brand only. Awaiting Windows gateway "
                    "verification before connect is enabled."
                ),
                "regions": ["Global"],
                "priority": 90,
            }
        )
    return sorted(
        rows,
        key=lambda r: (0 if r["connectable"] else 1, r["priority"], r["slug"]),
    )


def verified_servers_for_broker(
    slug: str,
    *,
    discovered: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return verified / discovered servers — never invented examples."""
    code = slug.strip().lower()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    if code == "weltrade":
        for row in _WELTRADE_VERIFIED:
            name = str(row["name"])
            seen.add(name.lower())
            out.append(dict(row))

    for raw in discovered or []:
        name = str(raw or "").strip()
        if not name or name.lower() in seen:
            continue
        matched = match_broker_for_server(name)
        if matched is not None and matched.slug != code:
            continue
        if matched is None and code != "weltrade":
            # Only accept undiscovered names when the broker slug is unknown
            # to the matcher — still require an explicit discovery feed.
            continue
        env = (
            "demo" if any(tok in name.lower() for tok in ("demo", "trial")) else "live"
        )
        out.append(
            {
                "name": name,
                "environment": env,
                "source": "mt5_terminal_discovery",
                "verified_at": _now_iso(),
            }
        )
        seen.add(name.lower())

    return out


def catalogue_snapshot(
    *,
    discovered_by_broker: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Full registry + per-broker server lists for Broker Accounts / Admin."""
    discovered_by_broker = discovered_by_broker or {}
    brokers = broker_registry_rows()
    servers: dict[str, list[dict[str, Any]]] = {}
    for row in brokers:
        slug = str(row["slug"])
        servers[slug] = verified_servers_for_broker(
            slug,
            discovered=discovered_by_broker.get(slug),
        )
    return {
        "brokers": brokers,
        "servers": servers,
        "gateway": {
            "requires_windows_mt5_terminal": True,
            "production_singleton": "weltrade_windows_gateway",
            "multi_broker_workers": "control_plane_present_not_live_for_extra_brokers",
            "note": (
                "Railway API alone cannot host MetaTrader 5. "
                "Extra brokers need isolated Windows workers with verified "
                "demo/live credentials before connectable=true."
            ),
        },
        "generated_at": _now_iso(),
    }


def documented_hints_for_admin(slug: str) -> list[str]:
    """Admin-only documented search hints — never shown as verified servers."""
    profile = profile_by_slug(slug)
    if profile is None:
        return []
    return list(profile.server_hints)
