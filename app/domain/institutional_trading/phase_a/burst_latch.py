"""Phase A per-minute / reject-burst latch — HALT_NEW_ENTRIES style cooldown."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class BurstLatchEvent:
    trigger: str
    window_s: float
    count: int
    threshold: int
    start_time: str
    cooldown_s: float
    release_time: str | None
    release_reason: str | None
    correlation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "window": self.window_s,
            "count": self.count,
            "threshold": self.threshold,
            "start_time": self.start_time,
            "cooldown": self.cooldown_s,
            "release_time": self.release_time,
            "release_reason": self.release_reason,
            "correlation_id": self.correlation_id,
        }


@dataclass
class BurstLatch:
    entry_window_s: float = 60.0
    max_entries_per_minute: int = 6
    reject_window_s: float = 120.0
    reject_threshold: int = 5
    failure_threshold: int = 5
    ambiguous_threshold: int = 3
    cooldown_s: float = 300.0

    _entries: deque[float] = field(default_factory=deque)
    _rejects: deque[float] = field(default_factory=deque)
    _failures: deque[float] = field(default_factory=deque)
    _ambiguous: deque[float] = field(default_factory=deque)
    latched_until: float = 0.0
    last_event: BurstLatchEvent | None = None
    history: list[BurstLatchEvent] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def _trim(self, q: deque[float], now: float, window: float) -> None:
        while q and (now - q[0]) > window:
            q.popleft()

    def is_latched(self, *, now: float | None = None) -> bool:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            return t < self.latched_until

    def remaining_cooldown_s(self, *, now: float | None = None) -> float:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            return max(0.0, self.latched_until - t)

    def _arm(
        self,
        *,
        trigger: str,
        count: int,
        threshold: int,
        window_s: float,
        now: float,
    ) -> BurstLatchEvent:
        start = datetime.now(UTC).isoformat()
        self.latched_until = now + float(self.cooldown_s)
        release_at = datetime.now(UTC).isoformat()
        ev = BurstLatchEvent(
            trigger=trigger,
            window_s=window_s,
            count=count,
            threshold=threshold,
            start_time=start,
            cooldown_s=float(self.cooldown_s),
            release_time=None,
            release_reason=None,
            correlation_id=str(uuid4()),
        )
        # store planned release wall time in history note via release_time later
        _ = release_at
        self.last_event = ev
        self.history.append(ev)
        if len(self.history) > 50:
            self.history = self.history[-50:]
        return ev

    def record_entry_attempt(self, *, now: float | None = None) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._trim(self._entries, t, self.entry_window_s)
            self._entries.append(t)
            if len(self._entries) >= int(self.max_entries_per_minute):
                return self._arm(
                    trigger="entry_burst",
                    count=len(self._entries),
                    threshold=int(self.max_entries_per_minute),
                    window_s=self.entry_window_s,
                    now=t,
                )
            return None

    def record_broker_reject(self, *, now: float | None = None) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._trim(self._rejects, t, self.reject_window_s)
            self._rejects.append(t)
            if len(self._rejects) >= int(self.reject_threshold):
                return self._arm(
                    trigger="broker_rejection_burst",
                    count=len(self._rejects),
                    threshold=int(self.reject_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                )
            return None

    def record_execution_failure(self, *, now: float | None = None) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._trim(self._failures, t, self.reject_window_s)
            self._failures.append(t)
            if len(self._failures) >= int(self.failure_threshold):
                return self._arm(
                    trigger="execution_failure_burst",
                    count=len(self._failures),
                    threshold=int(self.failure_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                )
            return None

    def record_ambiguous(self, *, now: float | None = None) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._trim(self._ambiguous, t, self.reject_window_s)
            self._ambiguous.append(t)
            if len(self._ambiguous) >= int(self.ambiguous_threshold):
                return self._arm(
                    trigger="ambiguous_order_burst",
                    count=len(self._ambiguous),
                    threshold=int(self.ambiguous_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                )
            return None

    def release(self, *, reason: str, now: float | None = None) -> None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self.latched_until = t
            if self.last_event is not None:
                self.last_event = BurstLatchEvent(
                    trigger=self.last_event.trigger,
                    window_s=self.last_event.window_s,
                    count=self.last_event.count,
                    threshold=self.last_event.threshold,
                    start_time=self.last_event.start_time,
                    cooldown_s=self.last_event.cooldown_s,
                    release_time=datetime.now(UTC).isoformat(),
                    release_reason=reason,
                    correlation_id=self.last_event.correlation_id,
                )

    def snapshot(self) -> dict[str, Any]:
        import time

        t = time.monotonic()
        with self._lock:
            self._trim(self._entries, t, self.entry_window_s)
            self._trim(self._rejects, t, self.reject_window_s)
            self._trim(self._failures, t, self.reject_window_s)
            self._trim(self._ambiguous, t, self.reject_window_s)
            return {
                "latched": t < self.latched_until,
                "remaining_cooldown_s": max(0.0, self.latched_until - t),
                "entries_last_60s": len(self._entries),
                "rejected_entries_last_window": len(self._rejects),
                "execution_failures_last_window": len(self._failures),
                "ambiguous_orders_last_window": len(self._ambiguous),
                "thresholds": {
                    "max_entries_per_minute": self.max_entries_per_minute,
                    "reject_burst_threshold": self.reject_threshold,
                    "failure_burst_threshold": self.failure_threshold,
                    "ambiguous_burst_threshold": self.ambiguous_threshold,
                    "cooldown_s": self.cooldown_s,
                },
                "last_event": self.last_event.to_dict() if self.last_event else None,
            }
