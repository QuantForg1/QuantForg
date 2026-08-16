"""Guard MT5 terminal access against cross-tenant session reuse."""

from __future__ import annotations

import contextlib
from typing import Any, cast
from uuid import UUID

from app.domain.entities.mt5 import MT5Connection
from app.domain.exceptions.base import NotFoundError
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.logging import get_logger

logger = get_logger(__name__)


def _is_gateway_backed(adapter: MT5Adapter) -> bool:
    """True when the adapter talks to a remote Windows gateway (shared terminal)."""
    return bool(getattr(adapter.client, "stores_credentials_remotely", False))


async def ensure_live_mt5_session_for_user(
    uow_factory: Any,
    adapter: MT5Adapter,
    user_id: UUID,
) -> MT5Connection | None:
    """Return a DB connection that is live on *this* worker.

    Railway workers only hold a process-local gateway session handle after
    adopt/attach. After redeploy (or when a different worker serves the
    request), ``/mt5/status`` and ticks would otherwise report disconnected
    even though the Windows gateway + MT5 session are healthy.

    Healing is limited to gateway-backed clients so in-process mock/local
    terminals keep strict cross-tenant isolation.
    """
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)

    if connection is not None and connection.connected:
        session_ref = (connection.session_ref or "").strip()
        if session_ref and adapter.is_live_session(session_ref):
            return cast("MT5Connection", connection)

    if not _is_gateway_backed(adapter):
        return None

    client = adapter.client
    with contextlib.suppress(Exception):
        adapter.health()

    if not getattr(client, "is_connected", False):
        return None

    live_ref = (getattr(adapter, "_live_session_ref", None) or "").strip()
    if not live_ref:
        live_ref = (getattr(client, "session_token", "") or "").strip()
    if not live_ref:
        try:
            live_ref = (adapter.attach(path="") or "").strip()
        except Exception as exc:
            logger.warning(
                "mt5_session_heal_attach_failed",
                error=str(exc),
                user_id=str(user_id),
            )
            return None
    if not live_ref or not adapter.is_live_session(live_ref):
        return None

    # Persist / refresh the DB row for this user (shared production terminal).
    resolved_login = 0
    resolved_server = ""
    with contextlib.suppress(Exception):
        info = adapter.account_info()
        resolved_login = int(getattr(info, "login", 0) or 0)
        resolved_server = str(getattr(info, "server", "") or "")
    if resolved_login <= 0 and live_ref in getattr(adapter, "_sessions", {}):
        stored = adapter._sessions.get(live_ref)
        if stored is not None:
            resolved_login = int(getattr(stored, "login", 0) or 0)
            resolved_server = str(getattr(stored, "server", "") or "")
    if resolved_login <= 0:
        resolved_login = int(getattr(connection, "login", 0) or 0) if connection else 0
    if not resolved_server:
        resolved_server = (
            str(getattr(connection, "server", "") or "") if connection else ""
        ) or "Weltrade-MT5"
    if resolved_login <= 0:
        resolved_login = 1

    build: int | None = None
    version = ""
    latency: float | None = None
    with contextlib.suppress(Exception):
        snap = adapter.health()
        build = snap.terminal_build
        version = snap.version or ""
        latency = snap.latency_ms

    healed = MT5Connection.create(
        user_id=user_id,
        login=resolved_login,
        server=resolved_server,
        terminal_path="",
    )
    healed.mark_connected(
        session_ref=live_ref,
        terminal_build=build,
        terminal_version=version,
        latency_ms=latency,
    )
    async with uow_factory() as uow:
        await uow.connections.upsert_for_user(healed)
        await uow.commit()
    logger.info(
        "mt5_session_healed",
        user_id=str(user_id),
        login=resolved_login,
        session_ref=live_ref[:24],
    )
    return healed


async def require_live_mt5_connection(
    uow_factory: Any,
    adapter: MT5Adapter,
    user_id: UUID,
) -> MT5Connection:
    """Require DB-active connection bound to this process terminal.

    A process-global MT5 terminal can only be logged in as one account at a time.
    Without this check, User A remaining ``connected`` in Postgres after User B
    reconnects would allow A to read B's account/positions.

    Gateway-backed deployments heal the process-local handle first so Terminal
    market data works after Railway worker rotation without a browser→localhost
    connection.
    """
    connection = await ensure_live_mt5_session_for_user(
        uow_factory, adapter, user_id
    )
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
    connection = await ensure_live_mt5_session_for_user(
        uow_factory, adapter, user_id
    )
    if connection is None or not connection.connected:
        return False, None
    session_ref = (connection.session_ref or "").strip()
    if not session_ref or not adapter.is_live_session(session_ref):
        return False, None
    return True, connection.login
