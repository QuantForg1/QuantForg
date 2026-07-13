"""Guard MT5 terminal access against cross-tenant session reuse."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from app.domain.entities.mt5 import MT5Connection
from app.domain.exceptions.base import NotFoundError
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


async def require_live_mt5_connection(
    uow_factory: Any,
    adapter: MT5Adapter,
    user_id: UUID,
) -> MT5Connection:
    """Require DB-active connection bound to this process terminal.

    A process-global MT5 terminal can only be logged in as one account at a time.
    Without this check, User A remaining ``connected`` in Postgres after User B
    reconnects would allow A to read B's account/positions.
    """
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)
    if connection is None or not connection.connected:
        raise NotFoundError("No active MT5 connection")
    session_ref = (connection.session_ref or "").strip()
    if not session_ref or not adapter.is_live_session(session_ref):
        raise NotFoundError(
            "No active MT5 connection",
            details={"reason": "terminal_session_mismatch"},
        )
    return cast("MT5Connection", connection)


async def live_connection_meta(
    uow_factory: Any,
    adapter: MT5Adapter,
    user_id: UUID,
) -> tuple[bool, int | None]:
    """Return ``(connected, login)`` only for a live matching session."""
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)
    if connection is None or not connection.connected:
        return False, None
    session_ref = (connection.session_ref or "").strip()
    if not session_ref or not adapter.is_live_session(session_ref):
        return False, None
    return True, connection.login
