"""Event-loop stall watchdog (diagnostics only).

A daemon thread schedules a no-op on the asyncio loop every second. If the
loop has not run it within ``threshold_s``, the loop thread is blocked by
synchronous work; the watchdog logs that thread's current stack once per
stall so the blocking call can be found from Production logs. It never
changes trading behaviour.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
import traceback

from core.logging import get_logger

logger = get_logger(__name__)

_started = False


def _stack_of(thread_id: int, limit: int = 18) -> list[str]:
    frame = sys._current_frames().get(thread_id)
    if frame is None:
        return []
    frames = traceback.extract_stack(frame)[-limit:]
    return [f"{f.filename.split('/app/', 1)[-1]}:{f.lineno} {f.name}" for f in frames]


def start_loop_watchdog(
    loop: asyncio.AbstractEventLoop, *, threshold_s: float = 3.0
) -> None:
    global _started
    if _started:
        return
    _started = True
    loop_thread_id = threading.get_ident()
    last_tick = [time.monotonic()]

    def _tick() -> None:
        last_tick[0] = time.monotonic()

    def _run() -> None:
        reported_for: float | None = None
        while not loop.is_closed():
            try:
                loop.call_soon_threadsafe(_tick)
            except RuntimeError:
                return
            time.sleep(1.0)
            lag = time.monotonic() - last_tick[0]
            if lag >= threshold_s and reported_for != last_tick[0]:
                reported_for = last_tick[0]
                logger.warning(
                    "event_loop_blocked",
                    blocked_s=round(lag, 1),
                    stack=_stack_of(loop_thread_id),
                )

    threading.Thread(target=_run, name="qf-loop-watchdog", daemon=True).start()
