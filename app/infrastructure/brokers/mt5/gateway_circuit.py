"""Per-endpoint circuit breaker for gateway reads.

When the Windows gateway stops answering one endpoint (16 Nov 2026: every
/history/deals call hung 60-140 s), each caller kept a worker thread busy for
the full timeout, the pool filled up and even /health/live took 20-120 s.

After ``FAILURES_TO_OPEN`` timeouts/unreachable errors on the same endpoint
family within ``WINDOW``, reads to that family fail immediately for
``OPEN_FOR`` seconds; one probe is then let through (half-open). Order
mutations are never short-circuited here. Callers already treat a gateway
error as "unknown" and fail closed.
"""

from __future__ import annotations

import threading
import time

FAILURES_TO_OPEN = 2
WINDOW = 180.0
OPEN_FOR = 60.0

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
_open_until: dict[str, float] = {}


def family(path: str) -> str:
    parts = [p for p in (path or "").split("/") if p]
    return parts[0] if parts else ""


def check(path: str, *, now: float | None = None) -> None:
    fam = family(path)
    t = time.monotonic() if now is None else now
    with _lock:
        until = _open_until.get(fam)
        if until is None:
            return
        if t < until:
            raise RuntimeError(
                f"Gateway circuit open for /{fam} ({int(until - t)}s): "
                "recent calls timed out; failing fast"
            )
        # Half-open: let this call probe; reopen on failure.
        _open_until.pop(fam, None)


def record_success(path: str) -> None:
    fam = family(path)
    with _lock:
        _failures.pop(fam, None)
        _open_until.pop(fam, None)


def record_failure(path: str, *, now: float | None = None) -> None:
    fam = family(path)
    t = time.monotonic() if now is None else now
    with _lock:
        recent = [x for x in _failures.get(fam, []) if t - x <= WINDOW]
        recent.append(t)
        _failures[fam] = recent
        if len(recent) >= FAILURES_TO_OPEN:
            _open_until[fam] = t + OPEN_FOR


def is_transport_failure(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "timeout" in msg or "timed out" in msg or "unreachable" in msg


def snapshot() -> dict[str, float]:
    t = time.monotonic()
    with _lock:
        return {k: round(v - t, 1) for k, v in _open_until.items() if v > t}


def reset_for_tests() -> None:
    with _lock:
        _failures.clear()
        _open_until.clear()
