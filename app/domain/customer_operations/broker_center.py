"""Broker Connection Center — never exposes credentials."""

from __future__ import annotations

from typing import Any

from app.domain.customer_operations.cop_persistence import JsonDocumentStore, utc_iso
from app.domain.customer_operations.production_readers import read_mt5_connections

_HISTORY: JsonDocumentStore | None = None


def _history() -> JsonDocumentStore:
    global _HISTORY
    if _HISTORY is None:
        _HISTORY = JsonDocumentStore("cop_broker_connection_history.json", "events")
    return _HISTORY


async def build_broker_connection_center() -> dict[str, Any]:
    connections = await read_mt5_connections()
    # Enrich connection history from append-only COP log (operator notes / probes)
    hist = list(reversed(_history().list(limit=100)))
    rows = []
    for c in connections:
        rows.append(
            {
                "broker": c.get("broker") or "MT5",
                "server": c.get("server"),
                "login": c.get("login_masked"),
                "connection_health": (
                    "healthy"
                    if c.get("connected") or str(c.get("status")).lower() in {
                        "connected",
                        "ok",
                        "healthy",
                    }
                    else str(c.get("status") or "unknown")
                ),
                "latency_ms": c.get("latency_ms"),
                "last_heartbeat": c.get("last_heartbeat"),
                "trading_permission": c.get("trading_permission"),
                "auto_trading_status": c.get("auto_trading_status"),
                "user_id": c.get("user_id"),
                "id": c.get("id"),
                "credentials_exposed": False,
            }
        )
    connected = sum(
        1
        for r in rows
        if str(r.get("connection_health")).lower() in {"healthy", "connected", "ok"}
    )
    return {
        "as_of": utc_iso(),
        "connections": rows,
        "count": len(rows),
        "connected": connected,
        "connection_history": hist,
        "credentials_exposed": False,
        "fabricated": False,
        "source": "public.mt5_connections",
        "note": "Login values are masked. Passwords/tokens never returned.",
    }
