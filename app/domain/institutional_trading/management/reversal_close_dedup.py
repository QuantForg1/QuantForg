"""Prevent duplicate LIVE reversal close requests for the same ticket.

In-memory only. A process restart may re-evaluate once; the PME/OMS path still
requires the position to be open on the broker before another close is sent.
"""

from __future__ import annotations

import time
from threading import Lock

_LOCK = Lock()
_PENDING: dict[int, float] = {}
_DEFAULT_COOLDOWN_SEC = 90.0


def should_allow_reversal_close(
    ticket: int,
    *,
    cooldown_sec: float = _DEFAULT_COOLDOWN_SEC,
) -> bool:
    """True when no recent close request is outstanding for ``ticket``."""
    tid = int(ticket)
    now = time.monotonic()
    with _LOCK:
        last = _PENDING.get(tid)
        if last is None:
            return True
        return (now - last) >= float(cooldown_sec)


def mark_reversal_close_requested(ticket: int) -> None:
    with _LOCK:
        _PENDING[int(ticket)] = time.monotonic()


def clear_reversal_close(ticket: int) -> None:
    with _LOCK:
        _PENDING.pop(int(ticket), None)


def reset_reversal_close_dedup_for_tests() -> None:
    with _LOCK:
        _PENDING.clear()
