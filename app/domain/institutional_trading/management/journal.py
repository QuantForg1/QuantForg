"""PME journal — every SL/TP/partial/trail/exit."""

from __future__ import annotations

from threading import Lock

from app.domain.institutional_trading.management.models import PositionManageRecord


class PositionManageJournal:
    def __init__(self, *, max_entries: int = 10000) -> None:
        self._lock = Lock()
        self._entries: list[PositionManageRecord] = []
        self._max = max_entries

    def append(self, entry: PositionManageRecord) -> PositionManageRecord:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max :]
            return entry

    def list(self, *, limit: int = 200) -> list[PositionManageRecord]:
        with self._lock:
            return list(self._entries[-limit:])

    def by_ticket(self, ticket: int) -> list[PositionManageRecord]:
        with self._lock:
            return [e for e in self._entries if e.ticket == ticket]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
