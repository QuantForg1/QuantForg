"""Verified MT5 broker / server catalogue for Broker Accounts.

Rules
-----
* Weltrade is marked ``production_verified`` from the LIVE gateway path.
* Other brokers become ``connectable`` only when Windows worker verification
  evidence records a successful authenticated session for that slug.
* Server rows always carry ``source`` + ``verified_at`` (or null when
  documented-only / not yet discovered).
* Documented ``server_hints`` from the ecosystem profile are NEVER returned
  as verified production servers.
* Live discovery / evidence may append servers observed on an attached MT5
  terminal for the matching broker slug.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.broker_connectivity.broker_verification_evidence import (
    connectable_slugs_from_evidence,
    discovered_servers_from_evidence,
    evidence_for_broker,
)
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
    evidence_connectable = connectable_slugs_from_evidence()
    rows: list[dict[str, Any]] = []
    for profile in sorted(MT5_ECOSYSTEM, key=lambda p: (p.priority, p.slug)):
        if profile.slug == "weltrade":
            verified = True
            status = "production_verified"
            notes = "Production Weltrade path via Windows MT5 Gateway."
        elif profile.slug in evidence_connectable:
            verified = True
            ev = evidence_for_broker(profile.slug) or {}
            status = str(ev.get("connection_status") or "demo_verified")
            notes = (
                "Windows MT5 worker verified an authenticated session for this "
                "broker. LIVE multi-account submit remains gated separately."
            )
        else:
            verified = False
            status = "not_verified"
            notes = (
                "Documented MT5 brand only. Connection is not marked "
                "operational until a QuantForg Windows gateway/worker "
                "verifies login for this broker."
            )
        rows.append(
            {
                "slug": profile.slug,
                "name": profile.name,
                "website": profile.website,
                "platform": "mt5",
                "connection_status": status,
                "connectable": verified,
                "notes": notes,
                "regions": list(profile.regions),
                "priority": profile.priority,
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

    # Evidence-backed servers from real Windows MT5 verifies.
    ev = evidence_for_broker(code)
    if ev:
        for server in ev.get("servers") or []:
            if not isinstance(server, dict):
                continue
            name = str(server.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            out.append(
                {
                    "name": name,
                    "environment": server.get("environment") or "demo",
                    "source": server.get("source") or "windows_mt5_demo_verify",
                    "verified_at": server.get("verified_at") or _now_iso(),
                }
            )
            seen.add(name.lower())

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
    discovered_by_broker = dict(discovered_by_broker or {})
    # Merge durable evidence discoveries without inventing names.
    for slug, names in discovered_servers_from_evidence().items():
        existing = list(discovered_by_broker.get(slug) or [])
        for name in names:
            if name not in existing:
                existing.append(name)
        discovered_by_broker[slug] = existing

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
            "multi_broker_workers": "control_plane_present_evidence_gated",
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
