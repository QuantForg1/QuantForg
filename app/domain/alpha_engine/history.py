"""Auditable Alpha Engine evaluation history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class AlphaHistoryStore:
    max_events: int = 200
    _events: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(self, result: dict[str, Any]) -> str:
        audit_id = f"ae_{uuid4().hex[:12]}"
        row = {
            "audit_id": audit_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            **result,
        }
        with self._lock:
            self._events.insert(0, row)
            if len(self._events) > self.max_events:
                self._events = self._events[: self.max_events]
        return audit_id

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events[: max(1, min(limit, self.max_events))])

    def get(self, audit_id: str) -> dict[str, Any] | None:
        with self._lock:
            for row in self._events:
                if row.get("audit_id") == audit_id:
                    return dict(row)
        return None
