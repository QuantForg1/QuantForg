"""Per-request trace of slow dependencies (diagnostics only).

The request middleware starts a trace; dependency clients (MT5 gateway,
Supabase auth, direct Postgres) record their calls. Slow requests then log a
breakdown, so latency work is driven by Production evidence.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

_trace: ContextVar[list[tuple[str, str, float]] | None] = ContextVar(
    "qf_request_trace", default=None
)


def start() -> Token[list[tuple[str, str, float]] | None]:
    return _trace.set([])


def reset(token: Token[list[tuple[str, str, float]] | None]) -> None:
    _trace.reset(token)


def record(kind: str, label: str, ms: float) -> None:
    calls = _trace.get()
    if calls is not None and len(calls) < 200:
        calls.append((kind, label, ms))


@contextmanager
def timed(kind: str, label: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        record(kind, label, (time.perf_counter() - t0) * 1000.0)


def summary() -> dict[str, Any]:
    calls = _trace.get() or []
    by_kind: dict[str, dict[str, float]] = {}
    for kind, _label, ms in calls:
        agg = by_kind.setdefault(kind, {"n": 0, "ms": 0.0})
        agg["n"] += 1
        agg["ms"] = round(agg["ms"] + ms, 1)
    slowest = sorted(calls, key=lambda c: c[2], reverse=True)[:6]
    return {
        "by_kind": by_kind,
        "slowest": [f"{k}:{lbl} {round(ms)}ms" for k, lbl, ms in slowest],
    }
