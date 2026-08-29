"""Authenticated execution context — one shared strategy, per-user account.

The live gateway remains a process-global singleton. This context records
*which QuantForg user* owns the currently attached broker session. It must
never invent a second engine, gateway, or scanner.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


def mask_broker_login(login: int | str | None) -> str:
    """Display-safe account identifier. Never returns a full login."""
    raw = str(login or "").strip()
    if not raw or raw in {"0", "1"}:
        return "••••"
    if len(raw) <= 4:
        return "••••"
    return f"{raw[:2]}•••{raw[-2:]}"


def mask_broker_server(server: str | None) -> str:
    """Display-safe server name — keep venue prefix, hide the rest."""
    raw = (server or "").strip()
    if not raw:
        return "—"
    if len(raw) <= 8:
        return raw
    return f"{raw[:8]}…"


@dataclass(frozen=True, slots=True)
class TradingContext:
    """Execution context from the authenticated user, never the client."""

    authenticated_user_id: UUID
    broker_connection_id: UUID | None = None
    broker_account_id: str = ""
    broker_server: str = ""
    connection_status: str = "NOT_CONNECTED"
    robot_status: str = "Stopped"
    trading_enabled: bool = False
    execution_permitted: bool = False

    @property
    def connected(self) -> bool:
        return self.connection_status in {"CONNECTED", "READY", "RUNNING", "DEGRADED"}
