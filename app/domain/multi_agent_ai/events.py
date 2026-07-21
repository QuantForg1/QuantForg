"""Agent event bus — agents communicate through auditable events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AgentEvent:
    event_id: str
    event_type: str
    agent: str
    payload: dict[str, Any]
    session_id: str
    created_at: str
    sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "agent": self.agent,
            "payload": dict(self.payload),
            "session_id": self.session_id,
            "created_at": self.created_at,
            "sequence": self.sequence,
            "auditable": True,
        }


Subscriber = Callable[[AgentEvent], None]


@dataclass
class AgentEventBus:
    """Append-only event bus for agent collaboration."""

    max_events: int = 2000
    _events: list[AgentEvent] = field(default_factory=list)
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
        agent: str,
        payload: dict[str, Any],
        session_id: str,
    ) -> AgentEvent:
        with self._lock:
            self._seq += 1
            event = AgentEvent(
                event_id=f"ae_{uuid4().hex[:12]}",
                event_type=event_type,
                agent=agent,
                payload=dict(payload),
                session_id=session_id,
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
        self, *, limit: int = 100, session_id: str | None = None
    ) -> list[AgentEvent]:
        with self._lock:
            rows = list(self._events)
        if session_id:
            rows = [e for e in rows if e.session_id == session_id]
        return rows[-max(1, min(limit, self.max_events)) :]

    def by_session(self, session_id: str) -> list[AgentEvent]:
        return self.list(limit=self.max_events, session_id=session_id)
