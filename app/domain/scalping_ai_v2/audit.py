"""Production audit records — every important event is explainable."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class ProductionAuditLog:
    """Bounded audit trail with correlation + execution identity."""

    max_entries: int = 2000
    _entries: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(
        self,
        *,
        module: str,
        severity: str,
        decision: str,
        reason: str,
        correlation_id: str,
        execution_identity: str | None = None,
        duration_ms: float | None = None,
        recovery_status: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "audit_id": f"au_{uuid4().hex[:12]}",
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": correlation_id,
            "execution_identity": execution_identity,
            "module": module,
            "severity": severity,
            "duration_ms": duration_ms,
            "decision": decision,
            "reason": reason,
            "recovery_status": recovery_status,
            "extra": dict(extra or {}),
        }
        with self._lock:
            self._entries.insert(0, row)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[: self.max_entries]
        return row

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries[: max(1, min(limit, self.max_entries))])

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
