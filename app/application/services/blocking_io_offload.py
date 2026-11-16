"""Bounded offload for sync Gateway / MT5 I/O.

Keeps the Uvicorn/FastAPI event loop free so ITE/scanner stalls cannot
block /health/live, /auth/me, or other lightweight handlers.

Does not change trading policy, Safety, Risk, OMS, or execution gates.
Does not create unbounded threads.
"""

from __future__ import annotations

import asyncio
import atexit
import contextvars
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, cast

# Match scanner parallel_scan_concurrency (4) plus one slot for a cycle
# overlapping execute_now. HTTP book reads keep asyncio.to_thread / the
# default executor so they are not queued behind ITE.
_MAX_WORKERS = 5
_executor: ThreadPoolExecutor | None = None


def blocking_io_pool_size() -> int:
    """Configured max workers for the ITE/scanner blocking I/O pool."""
    return _MAX_WORKERS


def get_blocking_io_executor() -> ThreadPoolExecutor:
    """Return the process-wide bounded executor (created once)."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="qf-blocking-io",
        )
    return _executor


def shutdown_blocking_io_executor(*, wait: bool = False) -> None:
    """Drop the pool on process shutdown. Safe to call more than once."""
    global _executor
    pool = _executor
    _executor = None
    if pool is not None:
        pool.shutdown(wait=wait, cancel_futures=False)


async def offload_blocking(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run a sync callable on the bounded ITE I/O pool.

    Use this for scanner / ITE / cycle Gateway work. Request-path book
    reads should keep ``asyncio.to_thread`` so they do not share this pool.
    """
    loop = asyncio.get_running_loop()
    executor = get_blocking_io_executor()
    if kwargs:
        bound = partial(fn, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)
    return await loop.run_in_executor(executor, fn, *args)


atexit.register(shutdown_blocking_io_executor)


# --- Isolated pools (16 Nov 2026 login-timeout root cause) ------------------
#
# Request-path broker reads (History, Portfolio, Weltrade health, Quant AI
# history) used ``asyncio.to_thread``: the *default* executor, shared with
# Supabase auth. When the gateway's /history/deals hung for 60-180 s, those
# threads filled the default pool and sign-in/refresh queued behind them
# (login 8.7 s, refresh 3.2 s, then "Request timed out" in the browser).
# Each class of I/O now has its own bounded pool, and broker reads fail fast
# instead of queueing without bound.


class _Pool:
    def __init__(self, name: str, workers: int, admit: int | None) -> None:
        self.name = name
        self.workers = workers
        self.admit = admit
        self._executor: ThreadPoolExecutor | None = None
        self._inflight = 0
        self._lock = threading.Lock()

    def executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.workers, thread_name_prefix=f"qf-{self.name}"
            )
        return self._executor

    @property
    def inflight(self) -> int:
        return self._inflight

    async def run[**P, T](
        self, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
    ) -> T:
        with self._lock:
            if self.admit is not None and self._inflight >= self.admit:
                from app.infrastructure.brokers.mt5.gateway_circuit import (
                    GatewayUnavailableError,
                )

                raise GatewayUnavailableError(
                    f"{self.name} capacity exhausted ({self._inflight} in flight); "
                    "failing fast"
                )
            self._inflight += 1
        call = partial(fn, *args, **kwargs) if kwargs else partial(fn, *args)
        # Carry context variables (gateway lane, request id) into the thread,
        # as asyncio.to_thread does.
        ctx = contextvars.copy_context()
        try:
            fut = self.executor().submit(ctx.run, call)
        except BaseException:
            self._release()
            raise
        # Count the thread until it really finishes: a caller that gives up
        # (wait_for timeout) must not free capacity a hung thread still holds.
        fut.add_done_callback(lambda _f: self._release())
        return cast("T", await asyncio.wrap_future(fut))

    def _release(self) -> None:
        with self._lock:
            self._inflight -= 1

    def shutdown(self) -> None:
        pool, self._executor = self._executor, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


AUTH_IO = _Pool("auth-io", workers=8, admit=None)
BROKER_READ = _Pool("broker-read", workers=8, admit=16)
RESEARCH_IO = _Pool("research-io", workers=4, admit=None)


async def run_auth_io[**P, T](
    fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    """Supabase auth calls: never share threads with broker I/O."""
    return await AUTH_IO.run(fn, *args, **kwargs)


async def run_broker_read[**P, T](
    fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    """Request-path gateway reads. Raises GatewayUnavailableError when full."""
    return await BROKER_READ.run(fn, *args, **kwargs)


async def run_research_io[**P, T](
    fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    """Research / catalogue scans (may queue; never blocks auth or reads)."""
    return await RESEARCH_IO.run(fn, *args, **kwargs)


def pool_stats() -> dict[str, dict[str, int | None]]:
    return {
        p.name: {"workers": p.workers, "inflight": p.inflight, "admit": p.admit}
        for p in (AUTH_IO, BROKER_READ, RESEARCH_IO)
    }


for _p in (AUTH_IO, BROKER_READ, RESEARCH_IO):
    atexit.register(_p.shutdown)
