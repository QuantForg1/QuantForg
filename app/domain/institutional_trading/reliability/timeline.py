"""Searchable / filterable / exportable audit timeline."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

from app.domain.institutional_trading.reliability.models import TimelineEvent


@dataclass
class AuditTimeline:
    _events: list[TimelineEvent] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_events: int = 50_000

    def append(self, event: TimelineEvent) -> TimelineEvent:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
            return event

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
    ) -> list[TimelineEvent]:
        with self._lock:
            rows = list(self._events)
        if category:
            rows = [e for e in rows if e.category == category]
        if severity:
            rows = [e for e in rows if e.severity == severity]
        if trace_id:
            rows = [e for e in rows if e.trace_id == trace_id]
        if since:
            rows = [e for e in rows if e.timestamp >= since]
        if until:
            rows = [e for e in rows if e.timestamp <= until]
        if q:
            ql = q.lower()
            rows = [
                e
                for e in rows
                if ql in e.action.lower()
                or ql in e.detail.lower()
                or ql in e.category.lower()
            ]
        return rows[-limit:]

    def export_json(self, events: list[TimelineEvent] | None = None) -> str:
        rows = events if events is not None else self.search(limit=10_000)
        return json.dumps([e.to_dict() for e in rows], indent=2)

    def export_csv(self, events: list[TimelineEvent] | None = None) -> str:
        rows = events if events is not None else self.search(limit=10_000)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "timestamp",
                "category",
                "action",
                "detail",
                "severity",
                "trace_id",
            ],
        )
        writer.writeheader()
        for e in rows:
            writer.writerow(e.to_dict())
        return buf.getvalue()

    def count(self) -> int:
        with self._lock:
            return len(self._events)
