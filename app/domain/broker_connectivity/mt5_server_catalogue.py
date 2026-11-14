"""Verified MT5 broker / server catalogue for Broker Accounts.

Rules
-----
* All documented MT5 brands are ``customer_selectable`` so customers can start
  a LIVE connection flow without waiting for internal DEMO verification.
* ``connectable`` / operational verification remains evidence-gated (admin honesty).
* Verified server rows always carry ``source`` + ``verified_at``.
* Documented ``server_hints`` are returned only as unconfirmed *candidates*
  (never as verified production servers).
* Live discovery / evidence may append servers observed on an authenticated MT5
  session for the matching broker slug — never cross-broker borrowing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

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
        "evidence_classification": "CONFIRMED",
    },
    {
        "name": "Weltrade-Demo",
        "environment": "demo",
        "source": "weltrade_profile_defaults",
        "verified_at": "2026-11-09T00:00:00+00:00",
        "evidence_classification": "CONFIRMED",
    },
)

# Portable LIVE authenticate+verify evidence (trade_mode=2) — never invent shards.
_EVIDENCE_VERIFIED_LIVE: dict[str, tuple[dict[str, Any], ...]] = {
    "xm": (
        {
            "name": "XMGlobal-MT5 20",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-13T08:13:21+00:00",
            "evidence_classification": "CONFIRMED",
        },
    ),
    "pepperstone": (
        {
            "name": "PepperstoneKE-MT5-Live01",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-13T10:36:00+00:00",
            "evidence_classification": "CONFIRMED",
        },
    ),
    # JustMarkets / Exness servers observed with trade_mode=2; master trading
    # password still required (investor/read-only was rejected).
    "justmarkets": (
        {
            "name": "JustMarkets-Live7",
            "environment": "live",
            "source": "windows_mt5_live_verify_readonly",
            "verified_at": "2026-11-13T10:30:00+00:00",
            "evidence_classification": "DOCUMENTED",
        },
    ),
    "exness": (
        {
            "name": "Exness-MT5Real10",
            "environment": "live",
            "source": "windows_mt5_live_verify_readonly",
            "verified_at": "2026-11-14T07:20:00+00:00",
            "evidence_classification": "DOCUMENTED",
        },
    ),
}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def classify_server_environment_hint(
    server: str,
) -> Literal["demo", "live", "unknown"]:
    """Heuristic only — never sole proof of account type."""
    low = (server or "").lower()
    if any(tok in low for tok in ("demo", "trial")):
        return "demo"
    if any(tok in low for tok in ("real", "live")):
        return "live"
    return "unknown"


def broker_registry_rows() -> list[dict[str, Any]]:
    """Customer + admin broker registry — selectable vs operationally verified."""
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
                "Authenticated MT5 session evidence exists for this broker. "
                "LIVE multi-account submit remains gated separately."
            )
        else:
            verified = False
            status = "not_verified"
            notes = (
                "Customers may select this broker and connect their own LIVE "
                "MT5 account. Operational verification evidence is recorded "
                "only after a successful gateway authenticate."
            )
        rows.append(
            {
                "slug": profile.slug,
                "name": profile.name,
                "website": profile.website,
                "platform": "mt5",
                "connection_status": status,
                "connectable": verified,
                # Customer UX: all documented brands are selectable for LIVE connect.
                "customer_selectable": True,
                "notes": notes,
                "regions": list(profile.regions),
                "priority": profile.priority,
            }
        )
    return sorted(
        rows,
        key=lambda r: (r["priority"], r["slug"]),
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
            payload = dict(row)
            payload["confirmed"] = True
            payload.setdefault("evidence_classification", "CONFIRMED")
            out.append(payload)

    for row in _EVIDENCE_VERIFIED_LIVE.get(code, ()):
        name = str(row["name"])
        if name.lower() in seen:
            continue
        payload = dict(row)
        # JustMarkets DOCUMENTED until master trading password verifies trade_allowed.
        payload["confirmed"] = payload.get("evidence_classification") == "CONFIRMED"
        out.append(payload)
        seen.add(name.lower())

    # Evidence-backed servers from real authenticated MT5 sessions.
    ev = evidence_for_broker(code)
    if ev:
        for server in ev.get("servers") or []:
            if not isinstance(server, dict):
                continue
            name = str(server.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            env_raw = str(server.get("environment") or "").lower()
            if env_raw not in {"demo", "live"}:
                # Refuse to invent environment for evidence without an explicit label.
                continue
            out.append(
                {
                    "name": name,
                    "environment": env_raw,
                    "source": server.get("source") or "windows_mt5_verify",
                    "verified_at": server.get("verified_at") or _now_iso(),
                    "confirmed": True,
                    "evidence_classification": "CONFIRMED",
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
        hint = classify_server_environment_hint(name)
        if hint == "unknown":
            # Do not invent live/demo from an ambiguous discovery name.
            continue
        out.append(
            {
                "name": name,
                "environment": hint,
                "source": "mt5_terminal_discovery",
                "verified_at": _now_iso(),
                "confirmed": True,
            }
        )
        seen.add(name.lower())

    return out


def candidate_servers_for_broker(slug: str) -> list[dict[str, Any]]:
    """Documented LIVE/DEMO search candidates — unconfirmed, never invented shards.

    Customers may pick a candidate as a starting point or type the exact portal
    server. Candidates are NOT verified connectivity evidence.
    """
    profile = profile_by_slug(slug)
    if profile is None:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in profile.server_hints:
        name = str(hint or "").strip()
        if not name or name.lower() in seen:
            continue
        matched = match_broker_for_server(name)
        if matched is None or matched.slug != profile.slug:
            continue
        env_hint = classify_server_environment_hint(name)
        if env_hint == "unknown":
            # Ambiguous documented prefixes (e.g. XMGlobal-MT5) stay candidates
            # without inventing LIVE — UI labels them as confirm-in-terminal.
            environment: Literal["demo", "live"] | None = None
        else:
            environment = env_hint
        out.append(
            {
                "name": name,
                "environment": environment,
                "source": "documented_candidate",
                "verified_at": None,
                "confirmed": False,
                "evidence_classification": "CANDIDATE",
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
    candidates: dict[str, list[dict[str, Any]]] = {}
    for row in brokers:
        slug = str(row["slug"])
        servers[slug] = verified_servers_for_broker(
            slug,
            discovered=discovered_by_broker.get(slug),
        )
        candidates[slug] = candidate_servers_for_broker(slug)
    return {
        "brokers": brokers,
        "servers": servers,
        "candidate_servers": candidates,
        "gateway": {
            "requires_windows_mt5_terminal": True,
            "production_singleton": "weltrade_windows_gateway",
            "multi_broker_workers": "control_plane_present_evidence_gated",
            "customer_live_connect": True,
            "note": (
                "Customers may connect their own LIVE MT5 accounts for any "
                "selectable broker. Automated LIVE trading submit remains gated. "
                "Documented candidates are not verified until authenticate succeeds."
            ),
        },
        "generated_at": _now_iso(),
    }


def documented_hints_for_admin(slug: str) -> list[str]:
    """Documented search hints — never shown as verified servers."""
    profile = profile_by_slug(slug)
    if profile is None:
        return []
    return list(profile.server_hints)
