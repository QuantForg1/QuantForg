"""Six-broker Demo/Live verification matrix — honest BLOCKED without credentials."""

from __future__ import annotations

from typing import Any

from app.domain.broker_connectivity.broker_verification_evidence import (
    evidence_for_broker,
    load_evidence,
)
from app.domain.broker_connectivity.mt5_server_catalogue import (
    broker_registry_rows,
    verified_servers_for_broker,
)

TARGET_BROKERS: tuple[str, ...] = (
    "exness",
    "hfm",
    "ic-markets",
    "pepperstone",
    "fp-markets",
    "xm",
)


def _env_status(entry: dict[str, Any] | None, environment: str) -> dict[str, Any]:
    if not entry:
        return {
            "status": "BLOCKED",
            "reason": "approved_credentials_not_provided",
            "verified_at": None,
            "server": None,
            "market_data": None,
            "account_validation": None,
            "worker_slot": None,
        }
    servers = [
        s
        for s in (entry.get("servers") or [])
        if isinstance(s, dict)
        and str(s.get("environment") or "").lower() == environment
    ]
    if not servers and entry.get("connectable") and environment == "demo":
        # Some evidence rows may omit environment; treat as demo if connectable.
        servers = [s for s in (entry.get("servers") or []) if isinstance(s, dict)]
    if not servers:
        return {
            "status": "BLOCKED",
            "reason": "no_verified_session_for_environment",
            "verified_at": entry.get("last_success_at"),
            "server": None,
            "market_data": None,
            "account_validation": None,
            "worker_slot": None,
        }
    latest = sorted(
        servers,
        key=lambda s: str(s.get("verified_at") or ""),
    )[-1]
    return {
        "status": "PASS",
        "reason": "",
        "verified_at": latest.get("verified_at"),
        "server": latest.get("name"),
        "market_data": latest.get("market_data_ok"),
        "account_validation": bool(latest.get("balance_observed")),
        "worker_slot": latest.get("slot_id"),
        "login_masked": latest.get("login_masked"),
    }


def build_verification_matrix() -> dict[str, Any]:
    registry = {r["slug"]: r for r in broker_registry_rows()}
    store = load_evidence()
    rows: list[dict[str, Any]] = []
    for slug in TARGET_BROKERS:
        meta = registry.get(slug) or {}
        entry = evidence_for_broker(slug)
        demo = _env_status(entry, "demo")
        live = _env_status(entry, "live")
        servers = verified_servers_for_broker(slug)
        rows.append(
            {
                "broker": slug,
                "name": meta.get("name") or slug,
                "connectable": bool(meta.get("connectable")),
                "connection_status": meta.get("connection_status") or "not_verified",
                "demo": demo,
                "live": live,
                "verified_servers": servers,
                "recovery": {
                    "status": (
                        "PASS"
                        if demo["status"] == "PASS" or live["status"] == "PASS"
                        else "BLOCKED"
                    ),
                    "reason": (
                        ""
                        if demo["status"] == "PASS" or live["status"] == "PASS"
                        else "requires_verified_session"
                    ),
                },
            }
        )
    return {
        "brokers": rows,
        "evidence_updated_at": store.get("updated_at"),
        "password_included": False,
        "live_orders_submitted": False,
        "note": (
            "PASS requires a real Windows MT5 authenticate+verify. "
            "BLOCKED means approved credentials or verified session are missing — "
            "not a simulated failure."
        ),
    }
