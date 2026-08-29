"""Guard MT5 terminal access against cross-tenant session reuse.

Gateway-backed production uses one Windows terminal. Railway holds a
process-local session handle after attach. Concurrent read endpoints must
share that handle — they must not treat a stale DB UUID as a disconnect,
and they must not each bootstrap MT5 independently.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, cast
from uuid import UUID

from app.domain.entities.mt5 import MT5Connection
from app.domain.exceptions.base import NotFoundError, ServiceUnavailableError
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.logging import get_logger

logger = get_logger(__name__)

# One heal at a time per process. Prevents status vs positions racing attach().
_heal_lock: asyncio.Lock | None = None
_heal_count = 0


def reset_session_heal_lock_for_tests() -> None:
    """Drop the process heal lock (unit tests that create new event loops)."""
    global _heal_lock, _heal_count
    _heal_lock = None
    _heal_count = 0


def session_heal_count() -> int:
    """How many Gateway attach/health heals ran in this process."""
    return _heal_count


def _heal_lock_for_loop() -> asyncio.Lock:
    global _heal_lock
    if _heal_lock is None:
        _heal_lock = asyncio.Lock()
    return _heal_lock


def _is_gateway_backed(adapter: MT5Adapter) -> bool:
    """True when the adapter talks to a remote Windows gateway (shared terminal)."""
    return bool(getattr(adapter.client, "stores_credentials_remotely", False))


def _client_connected(adapter: MT5Adapter) -> bool:
    return bool(getattr(adapter.client, "is_connected", False))


def _live_ref(adapter: MT5Adapter) -> str:
    ref = (getattr(adapter, "_live_session_ref", None) or "").strip()
    if ref:
        return ref
    return (getattr(adapter.client, "session_token", "") or "").strip()


def _live_account_login(adapter: MT5Adapter) -> int:
    """Login currently attached on the shared terminal. 0 if unknown (fail closed).

    Hot path: in-process session cache / client fields only. Never call
    ``account_info()`` here — that is a network round-trip on every status poll.
    """
    live = _live_ref(adapter)
    if live and live in getattr(adapter, "_sessions", {}):
        stored = adapter._sessions.get(live)
        login = int(getattr(stored, "login", 0) or 0) if stored is not None else 0
        if login > 1:
            return login
    client = adapter.client
    login = int(getattr(client, "_login", 0) or 0)
    if login > 1:
        return login
    return 0


def _owns_live_terminal(connection: MT5Connection, adapter: MT5Adapter) -> bool:
    """True only when this user's stored login matches the live terminal login.

    A process-global MT5 terminal can hold one account. Matching login is the
    ownership gate — never remap User B onto User A's live session.
    """
    owned = int(getattr(connection, "login", 0) or 0)
    if owned <= 1:
        return False
    live_login = _live_account_login(adapter)
    if live_login <= 1:
        return False
    return owned == live_login


async def _adapter_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run blocking Gateway/MT5 I/O off the asyncio event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)


def _bind_connection_to_live(
    connection: MT5Connection | None,
    adapter: MT5Adapter,
) -> MT5Connection | None:
    """Reuse the process-local handle instead of treating a DB UUID miss as down.

    Remap is Gateway-only. In-process mock/local terminals keep strict
    session_ref isolation so User A cannot read User B's login.
    """
    if connection is None or not connection.connected:
        return None
    if not _owns_live_terminal(connection, adapter):
        return None
    session_ref = (connection.session_ref or "").strip()
    if adapter.is_live_session(session_ref):
        return connection
    if not _is_gateway_backed(adapter):
        return None
    live = _live_ref(adapter)
    if not live or not _client_connected(adapter):
        return None
    if session_ref != live:
        connection.mark_connected(
            session_ref=live,
            terminal_build=connection.terminal_build,
            terminal_version=connection.terminal_version or "",
            latency_ms=connection.latency_ms,
        )
    return connection if adapter.is_live_session(live) else None


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

    Concurrent callers share one heal (single-flight). A process that already
    holds a live Gateway handle remaps a stale DB ``session_ref`` instead of
    raising a false disconnect.
    """
    t0 = time.perf_counter()
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)
    db_ms = (time.perf_counter() - t0) * 1000.0

    bound = _bind_connection_to_live(connection, adapter)
    if bound is not None and adapter.is_live_session((bound.session_ref or "").strip()):
        logger.debug(
            "mt5_session_fast_path",
            user_id=str(user_id),
            db_ms=round(db_ms, 1),
            server_ms=round((time.perf_counter() - t0) * 1000.0, 1),
        )
        return bound

    if connection is None:
        logger.info(
            "mt5_session_heal_skipped_no_owned_connection",
            user_id=str(user_id),
        )
        return None

    if not _is_gateway_backed(adapter):
        return None

    lock = _heal_lock_for_loop()
    async with lock:
        async with uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(user_id)
        bound = _bind_connection_to_live(connection, adapter)
        if bound is not None and adapter.is_live_session(
            (bound.session_ref or "").strip()
        ):
            return bound
        healed = await _heal_gateway_session(
            uow_factory=uow_factory,
            adapter=adapter,
            user_id=user_id,
            connection=connection,
            started=t0,
            db_ms=db_ms,
        )
        return healed


async def _heal_gateway_session(
    *,
    uow_factory: Any,
    adapter: MT5Adapter,
    user_id: UUID,
    connection: MT5Connection | None,
    started: float,
    db_ms: float,
) -> MT5Connection | None:
    global _heal_count
    client = adapter.client
    gw_t0 = time.perf_counter()
    with contextlib.suppress(Exception):
        await _adapter_call(adapter.health)
    gateway_ms = (time.perf_counter() - gw_t0) * 1000.0

    if not getattr(client, "is_connected", False):
        logger.info(
            "mt5_session_heal_skipped_disconnected",
            user_id=str(user_id),
            db_ms=round(db_ms, 1),
            gateway_ms=round(gateway_ms, 1),
            server_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        return None

    live_ref = _live_ref(adapter)
    mt5_ms = 0.0
    if not live_ref:
        mt5_t0 = time.perf_counter()
        try:
            live_ref = ((await _adapter_call(adapter.attach, path="")) or "").strip()
        except Exception as exc:
            logger.warning(
                "mt5_session_heal_attach_failed",
                error=str(exc),
                user_id=str(user_id),
            )
            return None
        mt5_ms = (time.perf_counter() - mt5_t0) * 1000.0
    if live_ref and not (getattr(adapter, "_live_session_ref", None) or "").strip():
        adapter._live_session_ref = live_ref
    if not live_ref or not adapter.is_live_session(live_ref):
        return None

    resolved_login = 0
    resolved_server = ""
    with contextlib.suppress(Exception):
        info = await _adapter_call(adapter.account_info)
        resolved_login = int(getattr(info, "login", 0) or 0)
        resolved_server = str(getattr(info, "server", "") or "")
    if resolved_login <= 1 and live_ref in getattr(adapter, "_sessions", {}):
        stored = adapter._sessions.get(live_ref)
        if stored is not None:
            resolved_login = int(getattr(stored, "login", 0) or 0)
            resolved_server = str(getattr(stored, "server", "") or "")
    owned_login = int(getattr(connection, "login", 0) or 0) if connection else 0
    owned_server = (
        str(getattr(connection, "server", "") or "") if connection else ""
    )
    if resolved_login <= 1:
        resolved_login = owned_login
    if not resolved_server:
        resolved_server = owned_server
    if (
        connection is None
        or owned_login <= 1
        or resolved_login <= 1
        or not resolved_server
    ):
        logger.info(
            "mt5_session_heal_skipped_unresolved_identity",
            user_id=str(user_id),
        )
        return None
    if owned_login != resolved_login:
        logger.info(
            "mt5_session_heal_skipped_login_mismatch",
            user_id=str(user_id),
            owned_login=owned_login,
            live_login=resolved_login,
        )
        return None

    _heal_count += 1

    build: int | None = None
    version = ""
    latency: float | None = None
    with contextlib.suppress(Exception):
        snap = await _adapter_call(adapter.health)
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
    persist_t0 = time.perf_counter()
    async with uow_factory() as uow:
        await uow.connections.upsert_for_user(healed)
        await uow.commit()
    persist_ms = (time.perf_counter() - persist_t0) * 1000.0
    logger.info(
        "mt5_session_healed",
        user_id=str(user_id),
        login=resolved_login,
        session_ref=live_ref[:24],
        db_ms=round(db_ms, 1),
        gateway_ms=round(gateway_ms, 1),
        mt5_ms=round(mt5_ms, 1),
        persist_ms=round(persist_ms, 1),
        server_ms=round((time.perf_counter() - started) * 1000.0, 1),
    )
    return healed


def _unavailable_for_failed_heal(adapter: MT5Adapter) -> ServiceUnavailableError:
    if _is_gateway_backed(adapter) and not _client_connected(adapter):
        # Distinguish tunnel vs terminal using last health if present.
        return ServiceUnavailableError(
            "MT5 terminal is not connected",
            code="MT5_UNAVAILABLE",
            details={"reason": "mt5_disconnected"},
        )
    if _is_gateway_backed(adapter):
        return ServiceUnavailableError(
            "MT5 Gateway is unavailable",
            code="GATEWAY_UNAVAILABLE",
            details={"reason": "gateway_unavailable"},
        )
    return ServiceUnavailableError(
        "MT5 session is unavailable",
        code="MT5_UNAVAILABLE",
        details={"reason": "session_unavailable"},
    )


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

    Session-cache misses on a healthy Gateway are healed, not mapped to 404.
    """
    connection = await ensure_live_mt5_session_for_user(
        uow_factory, adapter, user_id
    )
    if connection is None or not connection.connected:
        if _is_gateway_backed(adapter) and not _client_connected(adapter):
            raise _unavailable_for_failed_heal(adapter)
        raise NotFoundError(
            "No active MT5 connection",
            details={"reason": "not_owner"},
        )
    session_ref = (connection.session_ref or "").strip()
    if not session_ref or not adapter.is_live_session(session_ref):
        # Process handle drifted after heal — try one remap, then fail closed.
        remapped = _bind_connection_to_live(connection, adapter)
        if remapped is not None and adapter.is_live_session(
            (remapped.session_ref or "").strip()
        ):
            return remapped
        if _is_gateway_backed(adapter):
            raise ServiceUnavailableError(
                "MT5 session is connecting",
                code="MT5_CONNECTING",
                details={"reason": "terminal_session_mismatch"},
            )
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
        remapped = _bind_connection_to_live(connection, adapter)
        if remapped is None or not adapter.is_live_session(
            (remapped.session_ref or "").strip()
        ):
            return False, None
        return True, remapped.login
    return True, connection.login
