"""Auditable in-memory Kernel event bus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class KernelEvent:
    event_id: str
    event_type: str
    stage: str
    payload: dict[str, Any]
    trace_id: str
    created_at: str
    sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "stage": self.stage,
            "payload": dict(self.payload),
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "sequence": self.sequence,
        }


Subscriber = Callable[[KernelEvent], None]


@dataclass
class KernelEventBus:
    """Append-only auditable bus — sync, in-process, never invents payloads."""

    max_events: int = 2000
    _events: list[KernelEvent] = field(default_factory=list)
    _subscribers: list[Subscriber] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)
    _seq: int = 0

    def subscribe(self, handler: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(handler)

    def publish(
        self,
        *,
        event_type: str,
        stage: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> KernelEvent:
        with self._lock:
            self._seq += 1
            event = KernelEvent(
                event_id=f"ke_{uuid4().hex[:12]}",
                event_type=event_type,
                stage=stage,
                payload=dict(payload),
                trace_id=trace_id,
                created_at=datetime.now(UTC).isoformat(),
                sequence=self._seq,
            )
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
            handlers = list(self._subscribers)
        for handler in handlers:
            handler(event)
        return event

    def list(
        self, *, limit: int = 100, trace_id: str | None = None
    ) -> list[KernelEvent]:
        with self._lock:
            rows = list(self._events)
        if trace_id:
            rows = [e for e in rows if e.trace_id == trace_id]
        return rows[-max(1, min(limit, self.max_events)) :]

    def by_trace(self, trace_id: str) -> list[KernelEvent]:
        return self.list(limit=self.max_events, trace_id=trace_id)
