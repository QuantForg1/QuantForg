"""Event-driven architecture — auditable in-process bus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

# Canonical event types (requirement 13)
EVENT_TYPES: tuple[str, ...] = (
    "MarketUpdated",
    "SignalGenerated",
    "DecisionApproved",
    "RiskApproved",
    "SafetyApproved",
    "ExecutionStarted",
    "BrokerFilled",
    "PositionOpened",
    "PositionClosed",
    "AnalyticsUpdated",
    "IncidentDetected",
    "RecoveryStarted",
    "RecoveryCompleted",
    "NoTrade",
    "WatchdogAlert",
    "DuplicateBlocked",
    "CycleCompleted",
)


@dataclass(frozen=True, slots=True)
class ScalpEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    cycle_id: str
    created_at: str
    sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "cycle_id": self.cycle_id,
            "created_at": self.created_at,
            "sequence": self.sequence,
            "auditable": True,
        }


Subscriber = Callable[[ScalpEvent], None]


@dataclass
class ScalpEventBus:
    max_events: int = 5000
    _events: list[ScalpEvent] = field(default_factory=list)
    _subscribers: list[Subscriber] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)
    _seq: int = 0

    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        cycle_id: str,
    ) -> ScalpEvent:
        with self._lock:
            self._seq += 1
            event = ScalpEvent(
                event_id=f"sx_{uuid4().hex[:12]}",
                event_type=event_type,
                payload=dict(payload),
                cycle_id=cycle_id,
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
        self, *, limit: int = 100, cycle_id: str | None = None
    ) -> list[ScalpEvent]:
        with self._lock:
            rows = list(self._events)
        if cycle_id:
            rows = [e for e in rows if e.cycle_id == cycle_id]
        return rows[-max(1, min(limit, self.max_events)) :]
