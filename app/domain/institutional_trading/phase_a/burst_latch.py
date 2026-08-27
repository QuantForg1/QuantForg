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
    last_event_stage: str | None = None

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
            "last_event_stage": self.last_event_stage,
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
    last_increment_stage: str | None = None
    last_increment_trigger: str | None = None
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

    def _note_increment(self, *, trigger: str, stage: str | None) -> None:
        self.last_increment_trigger = trigger
        if stage:
            self.last_increment_stage = stage

    def blocking_gate_name(self) -> str:
        trigger = ""
        if self.last_event is not None:
            trigger = str(self.last_event.trigger or "")
        if trigger == "entry_burst":
            return "ENTRY_BURST"
        return "EXECUTION_REJECT_BURST"

    def _arm(
        self,
        *,
        trigger: str,
        count: int,
        threshold: int,
        window_s: float,
        now: float,
        stage: str | None = None,
    ) -> BurstLatchEvent:
        start = datetime.now(UTC).isoformat()
        self.latched_until = now + float(self.cooldown_s)
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
            last_event_stage=stage or self.last_increment_stage,
        )
        self.last_event = ev
        self.history.append(ev)
        if len(self.history) > 50:
            self.history = self.history[-50:]
        return ev

    def record_entry_attempt(self, *, now: float | None = None) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._note_increment(trigger="entry_attempt", stage="OMS_SUCCESS")
            self._trim(self._entries, t, self.entry_window_s)
            self._entries.append(t)
            if len(self._entries) >= int(self.max_entries_per_minute):
                return self._arm(
                    trigger="entry_burst",
                    count=len(self._entries),
                    threshold=int(self.max_entries_per_minute),
                    window_s=self.entry_window_s,
                    now=t,
                    stage="OMS_SUCCESS",
                )
            return None

    def record_broker_reject(
        self, *, now: float | None = None, stage: str | None = None
    ) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._note_increment(trigger="broker_reject", stage=stage)
            self._trim(self._rejects, t, self.reject_window_s)
            self._rejects.append(t)
            if len(self._rejects) >= int(self.reject_threshold):
                return self._arm(
                    trigger="broker_rejection_burst",
                    count=len(self._rejects),
                    threshold=int(self.reject_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                    stage=stage,
                )
            return None

    def record_execution_failure(
        self, *, now: float | None = None, stage: str | None = None
    ) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._note_increment(trigger="execution_failure", stage=stage)
            self._trim(self._failures, t, self.reject_window_s)
            self._failures.append(t)
            if len(self._failures) >= int(self.failure_threshold):
                return self._arm(
                    trigger="execution_failure_burst",
                    count=len(self._failures),
                    threshold=int(self.failure_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                    stage=stage,
                )
            return None

    def record_ambiguous(
        self, *, now: float | None = None, stage: str | None = None
    ) -> BurstLatchEvent | None:
        import time

        t = now if now is not None else time.monotonic()
        with self._lock:
            self._note_increment(trigger="ambiguous", stage=stage)
            self._trim(self._ambiguous, t, self.reject_window_s)
            self._ambiguous.append(t)
            if len(self._ambiguous) >= int(self.ambiguous_threshold):
                return self._arm(
                    trigger="ambiguous_order_burst",
                    count=len(self._ambiguous),
                    threshold=int(self.ambiguous_threshold),
                    window_s=self.reject_window_s,
                    now=t,
                    stage=stage,
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
                    last_event_stage=self.last_event.last_event_stage,
                )

    def snapshot(self) -> dict[str, Any]:
        import time

        t = time.monotonic()
        with self._lock:
            self._trim(self._entries, t, self.entry_window_s)
            self._trim(self._rejects, t, self.reject_window_s)
            self._trim(self._failures, t, self.reject_window_s)
            self._trim(self._ambiguous, t, self.reject_window_s)
            remaining = max(0.0, self.latched_until - t)
            latched = t < self.latched_until
            trigger = (
                str(self.last_event.trigger) if self.last_event is not None else ""
            )
            reject_active = latched and trigger != "entry_burst"
            last_stage = self.last_increment_stage
            if self.last_event is not None and self.last_event.last_event_stage:
                last_stage = self.last_event.last_event_stage
            reject_burst = {
                "active": bool(reject_active),
                "count": len(self._rejects),
                "window": self.reject_window_s,
                "last_event": (
                    self.last_event.to_dict()
                    if self.last_event
                    else self.last_increment_trigger
                ),
                "last_event_stage": last_stage,
                "clear_condition": (
                    f"autonomous cooldown {float(self.cooldown_s):.0f}s "
                    "(fill not required; windowed rejects expire with the window)"
                ),
                "remaining_cooldown": remaining if reject_active else 0.0,
            }
            return {
                "latched": latched,
                "remaining_cooldown_s": remaining,
                "blocking_gate": self.blocking_gate_name() if latched else None,
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
                "reject_burst": reject_burst,
            }
