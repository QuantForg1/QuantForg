"""Broker diagnostics from supplied connection facts only."""

from __future__ import annotations

from typing import Any


def build_broker_diagnostics(
    *,
    connected: bool | None,
    status: str | None,
    latency_ms: float | None,
    last_heartbeat_at: str | None,
    last_disconnect_reason: str | None,
    reconnect_events: list[dict[str, Any]] | None,
    uptime_seconds: float | None,
) -> dict[str, Any]:
    reconnects = list(reconnect_events or [])
    return {
        "connection": {
            "connected": connected,
            "status": status or ("unknown" if connected is None else None),
            "status_source": "mt5_status|broker_health",
        },
        "heartbeat": {
            "last_heartbeat_at": last_heartbeat_at,
            "status": "available" if last_heartbeat_at else "unavailable",
            "reason": (
                None if last_heartbeat_at else "No heartbeat timestamp supplied"
            ),
        },
        "gateway_latency_ms": latency_ms,
        "gateway_latency_status": (
            "available" if latency_ms is not None else "unavailable"
        ),
        "gateway_latency_reason": (
            None if latency_ms is not None else "No latency_ms on connection status"
        ),
        "uptime_seconds": uptime_seconds,
        "uptime_status": (
            "available" if uptime_seconds is not None else "unavailable"
        ),
        "last_disconnect_reason": last_disconnect_reason,
        "last_disconnect_status": (
            "available" if last_disconnect_reason else "unavailable"
        ),
        "reconnect_history": reconnects,
        "reconnect_count": len(reconnects),
        "reconnect_history_status": (
            "available" if reconnects else "unavailable"
        ),
        "note": "Diagnostics never invent disconnect/reconnect events",
    }
