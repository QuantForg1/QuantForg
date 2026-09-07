"""Sync-safe direct Postgres for ops/telemetry (no PostgREST).

Uses the same DATABASE_URL / pooler as SQLAlchemy. Counts as database
traffic, not Supabase API egress. Never authorizes live trading.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_LOOP: asyncio.AbstractEventLoop | None = None
_THREAD: threading.Thread | None = None
_POOL: Any = None


def reset_direct_postgres_for_tests() -> None:
    """Drop the background pool (unit tests)."""
    global _LOOP, _THREAD, _POOL
    with _LOCK:
        pool = _POOL
        loop = _LOOP
        _POOL = None
        if pool is not None and loop is not None and loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(pool.close(), loop)
                fut.result(timeout=3)
            except Exception as exc:
                logger.debug("direct_postgres_pool_close_failed", error=str(exc))
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        _LOOP = None
        _THREAD = None


def direct_postgres_available() -> bool:
    """True when durable DATABASE_URL exists and this is not a test process."""
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return False
    if bool(getattr(settings, "is_testing", False)):
        return False
    if not bool(getattr(settings, "durable_persistence", True)):
        return False
    url = str(getattr(settings, "database_url", "") or "").strip()
    return bool(url)


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _LOOP, _THREAD
    with _LOCK:
        if _LOOP is not None and _THREAD is not None and _THREAD.is_alive():
            return _LOOP
        ready = threading.Event()

        def _runner() -> None:
            global _LOOP
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _LOOP = loop
            ready.set()
            loop.run_forever()

        _THREAD = threading.Thread(
            target=_runner, name="quantforg-direct-pg", daemon=True
        )
        _THREAD.start()
        if not ready.wait(timeout=5):
            msg = "direct postgres loop failed to start"
            raise RuntimeError(msg)
        assert _LOOP is not None
        return _LOOP


def _run(coro: Any, *, timeout: float = 8.0) -> Any:
    loop = _ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=timeout)


async def _ensure_pool() -> Any:
    global _POOL
    if _POOL is not None:
        return _POOL
    import asyncpg

    from core.config.settings import get_settings

    settings = get_settings()
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    kwargs: dict[str, Any] = {"min_size": 1, "max_size": 2, "timeout": 8}
    args = settings.asyncpg_connect_args
    if "ssl" in args:
        kwargs["ssl"] = args["ssl"]
    if args.get("statement_cache_size") == 0:
        kwargs["statement_cache_size"] = 0
    _POOL = await asyncpg.create_pool(url, **kwargs)
    return _POOL


def fetch(query: str, *args: Any, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Run a SELECT and return dict rows. Empty list when unavailable."""
    if not direct_postgres_available():
        return []

    async def _go() -> list[dict[str, Any]]:
        pool = await _ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    try:
        return _run(_go(), timeout=timeout)
    except Exception:
        logger.warning("direct_postgres_fetch_failed", query=query[:80])
        raise


def execute(query: str, *args: Any, timeout: float = 8.0) -> str:
    """Run INSERT/UPDATE/DELETE. Returns command status."""
    if not direct_postgres_available():
        return ""

    async def _go() -> str:
        pool = await _ensure_pool()
        async with pool.acquire() as conn:
            return str(await conn.execute(query, *args))

    try:
        return _run(_go(), timeout=timeout)
    except Exception:
        logger.warning("direct_postgres_execute_failed", query=query[:80])
        raise


def executemany(
    query: str, args_seq: Sequence[Sequence[Any]], *, timeout: float = 12.0
) -> int:
    """Run a parameterized statement for each arg tuple. Returns row attempts."""
    if not direct_postgres_available() or not args_seq:
        return 0

    async def _go() -> int:
        pool = await _ensure_pool()
        async with pool.acquire() as conn:
            await conn.executemany(query, list(args_seq))
            return len(args_seq)

    try:
        return _run(_go(), timeout=timeout)
    except Exception:
        logger.warning("direct_postgres_executemany_failed", query=query[:80])
        raise
