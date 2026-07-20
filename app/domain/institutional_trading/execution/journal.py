"""Phase C execution attempt journal — every bridge evaluation is persisted."""

from __future__ import annotations

from threading import Lock

from app.domain.institutional_trading.execution.models import ExecutionAttemptRecord


class ExecutionAttemptJournal:
    """Process-scoped journal for ITE execution attempts (separate from OMS blotter)."""

    def __init__(self, *, max_entries: int = 5000) -> None:
        self._lock = Lock()
        self._entries: list[ExecutionAttemptRecord] = []
        self._max = max_entries

    def append(self, entry: ExecutionAttemptRecord) -> ExecutionAttemptRecord:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max :]
            return entry

    def list(self, *, limit: int = 100) -> list[ExecutionAttemptRecord]:
        with self._lock:
            return list(self._entries[-limit:])

    def by_decision_hash(self, decision_hash: str) -> list[ExecutionAttemptRecord]:
        with self._lock:
            return [e for e in self._entries if e.decision_hash == decision_hash]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
