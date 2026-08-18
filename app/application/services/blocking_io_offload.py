"""Bounded offload for sync Gateway / MT5 I/O.

Keeps the Uvicorn/FastAPI event loop free so ITE/scanner stalls cannot
block /health/live, /auth/me, or other lightweight handlers.

Does not change trading policy, Safety, Risk, OMS, or execution gates.
Does not create unbounded threads.
"""

from __future__ import annotations

import asyncio
import atexit
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

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
