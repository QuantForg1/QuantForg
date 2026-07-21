"""Auditable readiness action log — failures and recoveries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ReadinessAuditEvent:
    event_id: str
    action: str
    ok: bool
    detail: str
    operator: str
    created_at: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action,
            "ok": self.ok,
            "detail": self.detail,
            "operator": self.operator,
            "created_at": self.created_at,
            "meta": dict(self.meta),
        }


@dataclass
class ReadinessAuditLog:
    max_events: int = 500
    _events: list[ReadinessAuditEvent] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(
        self,
        *,
        action: str,
        ok: bool,
        detail: str,
        operator: str = "system",
        meta: dict[str, Any] | None = None,
    ) -> ReadinessAuditEvent:
        event = ReadinessAuditEvent(
            event_id=f"pra_{uuid4().hex[:12]}",
            action=action.strip() or "unknown",
            ok=bool(ok),
            detail=(detail or "")[:2000],
            operator=(operator or "system")[:120],
            created_at=datetime.now(UTC).isoformat(),
            meta=dict(meta or {}),
        )
        with self._lock:
            self._events.insert(0, event)
            if len(self._events) > self.max_events:
                self._events = self._events[: self.max_events]
        return event

    def list(self, *, limit: int = 50) -> list[ReadinessAuditEvent]:
        with self._lock:
            return list(self._events[: max(1, min(limit, self.max_events))])
