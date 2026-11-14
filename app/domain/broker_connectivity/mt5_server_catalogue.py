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
            "trade_allowed": True,
        },
    ),
    "ic-markets": (
        {
            "name": "ICMarketsSC-MT5-3",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-14T08:40:33+00:00",
            "evidence_classification": "CONFIRMED",
            "trade_allowed": True,
        },
    ),
    "fp-markets": (
        {
            "name": "FPMarketsSC-Live",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-14T08:41:50+00:00",
            "evidence_classification": "CONFIRMED",
            "trade_allowed": True,
        },
    ),
    # Authenticated LIVE sessions (Windows portable verify 2026-11-14).
    # trade_allowed remains False until MT5 account_info.trade_allowed is true —
    # never manufacture trading permission from owner enablement alone.
    "justmarkets": (
        {
            "name": "JustMarkets-Live7",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-14T08:39:00+00:00",
            "evidence_classification": "CONFIRMED",
            "verification_method": "WINDOWS_MT5_VERIFY",
            "trading_readiness": "AUTH_OK_TRADE_NOT_ENABLED",
            "trade_allowed": False,
        },
    ),
    "exness": (
        {
            "name": "Exness-MT5Real10",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-14T08:37:00+00:00",
            "evidence_classification": "CONFIRMED",
            "verification_method": "WINDOWS_MT5_VERIFY",
            "trading_readiness": "AUTH_OK_TRADE_NOT_ENABLED",
            "trade_allowed": False,
        },
    ),
    "hfm": (
        {
            "name": "HFMarketsGlobal-Live20",
            "environment": "live",
            "source": "windows_mt5_live_verify",
            "verified_at": "2026-11-14T08:38:00+00:00",
            "evidence_classification": "CONFIRMED",
            "verification_method": "WINDOWS_MT5_VERIFY",
            "trading_readiness": "AUTH_OK_TRADE_NOT_ENABLED",
            "trade_allowed": False,
        },
    ),
}

# Brokers with genuine MT5 trade_allowed=true evidence (portable LIVE verify).
_GENUINE_MT5_TRADE_ALLOWED: frozenset[str] = frozenset(
    {
        "xm",
        "ic-markets",
        "pepperstone",
        "fp-markets",
    }
)

# Authenticated LIVE (correct login/server) but MT5 trade_allowed=false —
# typically unfunded / broker activation pending. Connectable + Verified UI OK;
# trading_enabled stays false until MT5 reports trade_allowed.
_AUTH_OK_TRADE_NOT_ENABLED: frozenset[str] = frozenset(
    {
        "exness",
        "hfm",
        "justmarkets",
    }
)

# Product-owner authorized LIVE connectable / Verified display set.
_OWNER_AUTHORIZED_LIVE_CONNECTABLE: frozenset[str] = frozenset(
    {
        "xm",
        "exness",
        "hfm",
        "justmarkets",
        "ic-markets",
        "pepperstone",
        "fp-markets",
    }
)


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


def _public_live_verification(
    *,
    trade_connectable: bool,
    trading_readiness: str,
    verification_method: str,
    trade_allowed: bool | None,
    notes: str,
) -> dict[str, Any]:
    """Consistent LIVE display status without inventing trade permission."""
    return {
        "connection_status": "live_verified",
        "verification_status": "VERIFIED_LIVE",
        "display_label": "Verified",
        "connectable": trade_connectable,
        "account_verified": True,
        "trading_readiness": trading_readiness,
        "verification_method": verification_method,
        "trade_allowed": (
            bool(trade_allowed) if trade_allowed is not None else trade_connectable
        ),
        "trading_enabled": bool(trade_connectable and trade_allowed),
        "notes": notes,
    }


def broker_registry_rows() -> list[dict[str, Any]]:
    """Customer + admin broker registry — selectable vs operationally verified."""
    evidence_connectable = connectable_slugs_from_evidence()
    rows: list[dict[str, Any]] = []
    for profile in sorted(MT5_ECOSYSTEM, key=lambda p: (p.priority, p.slug)):
        ev = evidence_for_broker(profile.slug) or {}
        ev_status = str(ev.get("connection_status") or "")
        owner_connectable = (
            bool(ev.get("owner_trade_enabled"))
            or (
                str(ev.get("verification_method") or "").upper()
                == "OWNER_TRADE_ENABLEMENT"
            )
            or (profile.slug in _OWNER_AUTHORIZED_LIVE_CONNECTABLE)
        )
        # Prefer durable MT5 evidence over owner display flags for permission.
        # Never treat OWNER_TRADE_ENABLEMENT as a substitute for MT5 trade_allowed.
        evidence_trade_allowed = ev.get("trade_allowed")
        method_upper = str(ev.get("verification_method") or "").upper()
        if profile.slug in _AUTH_OK_TRADE_NOT_ENABLED:
            if (
                method_upper in {"WINDOWS_MT5_VERIFY", "WINDOWS_MT5_LIVE_VERIFY"}
                and evidence_trade_allowed is True
            ):
                pass  # genuine re-verify after funding/activation
            else:
                evidence_trade_allowed = False
        elif (
            evidence_trade_allowed is None
            and profile.slug in _GENUINE_MT5_TRADE_ALLOWED
        ):
            evidence_trade_allowed = True

        if profile.slug == "weltrade":
            public = {
                "connection_status": "production_verified",
                "verification_status": "VERIFIED_LIVE",
                "display_label": "Verified",
                "connectable": True,
                "account_verified": True,
                "trading_readiness": "READY",
                "verification_method": "PRODUCTION_GATEWAY",
                "trade_allowed": True,
                "trading_enabled": True,
                "notes": "Production Weltrade path via Windows MT5 Gateway.",
            }
        elif profile.slug in evidence_connectable or owner_connectable:
            raw = ev_status or "live_verified"
            if raw == "demo_verified" and profile.slug in evidence_connectable:
                public = {
                    "connection_status": "demo_verified",
                    "verification_status": "VERIFIED_DEMO",
                    "display_label": "Verified",
                    "connectable": True,
                    "account_verified": True,
                    "trading_readiness": str(ev.get("trading_readiness") or "READY"),
                    "verification_method": str(
                        ev.get("verification_method") or "WINDOWS_MT5_VERIFY"
                    ),
                    "trade_allowed": True,
                    "trading_enabled": True,
                    "notes": (
                        "Authenticated MT5 session evidence exists for this broker. "
                        "LIVE multi-account submit remains gated separately."
                    ),
                }
            else:
                genuine_trade = bool(evidence_trade_allowed)
                method = str(
                    ev.get("verification_method") or "WINDOWS_MT5_VERIFY"
                )
                readiness = str(
                    ev.get("trading_readiness")
                    or (
                        "READY"
                        if genuine_trade
                        else "AUTH_OK_TRADE_NOT_ENABLED"
                    )
                )
                public = _public_live_verification(
                    trade_connectable=True,
                    trading_readiness=readiness,
                    verification_method=method,
                    trade_allowed=genuine_trade,
                    notes=(
                        "LIVE broker is Verified and connectable. "
                        "Trading permission reflects MT5 account_info.trade_allowed "
                        "(never manufactured). Global LIVE submit kill-switches "
                        "remain separate host configuration."
                        if genuine_trade
                        else (
                            "LIVE login/server authenticated; MT5 reports "
                            "trade_allowed=false (fund/activate at broker, then "
                            "re-verify). Global LIVE submit remains gated."
                        )
                    ),
                )
        else:
            public = {
                "connection_status": "not_verified",
                "verification_status": "NOT_VERIFIED",
                "display_label": "Not verified",
                "connectable": False,
                "account_verified": False,
                "trading_readiness": "",
                "verification_method": "",
                "trade_allowed": False,
                "trading_enabled": False,
                "notes": (
                    "Customers may select this broker and connect their own LIVE "
                    "MT5 account. Operational verification evidence is recorded "
                    "only after a successful gateway authenticate."
                ),
            }
        rows.append(
            {
                "slug": profile.slug,
                "name": profile.name,
                "website": profile.website,
                "platform": "mt5",
                # Customer UX: all documented brands are selectable for LIVE connect.
                "customer_selectable": True,
                "regions": list(profile.regions),
                "priority": profile.priority,
                **public,
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
