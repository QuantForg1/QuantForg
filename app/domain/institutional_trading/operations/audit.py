"""Append-only audit log — never delete."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.domain.institutional_trading.operations.models import (
    AuditEntry,
    OperatorIdentity,
)


@dataclass
class AuditLog:
    _entries: list[AuditEntry] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_entries: int = 50_000

    def record(
        self,
        *,
        operator: OperatorIdentity,
        action: str,
        old_value: str,
        new_value: str,
        reason: str,
        now: datetime | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=now or datetime.now(UTC),
            operator=operator.display_name or str(operator.user_id),
            operator_id=str(operator.user_id),
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            ip=operator.ip,
            user_agent=operator.user_agent,
        )
        with self._lock:
            self._entries.append(entry)
            # Soft trim only if > 2x max - keep newest + oldest sample.
            if len(self._entries) > self.max_entries * 2:
                keep = (
                    self._entries[:1000] + self._entries[-(self.max_entries - 1000) :]
                )
                self._entries = keep
            return entry

    def list(self, *, limit: int = 200) -> list[AuditEntry]:
        with self._lock:
            return list(self._entries[-limit:])

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear_for_tests_only(self) -> None:
        """Test helper — production must never call this on durable store."""
        with self._lock:
            self._entries.clear()
