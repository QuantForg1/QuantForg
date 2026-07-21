"""AI Memory — observations and reports only; never rewrites trading rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    kind: str
    agent: str
    content: dict[str, Any]
    session_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "agent": self.agent,
            "content": dict(self.content),
            "session_id": self.session_id,
            "created_at": self.created_at,
            "rewrites_rules": False,
        }


@dataclass
class AIMemory:
    """Store observations and reports. Hard-locked against rule mutation."""

    max_memory: int = 500
    _records: list[MemoryRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)
    rewrite_attempts: int = 0

    def store(
        self,
        *,
        kind: str,
        agent: str,
        content: dict[str, Any],
        session_id: str | None = None,
    ) -> MemoryRecord | dict[str, Any]:
        # Reject any attempt to rewrite trading rules.
        if kind in {"rule", "policy_rewrite", "trading_rule", "bypass"}:
            self.rewrite_attempts += 1
            return {
                "status": "rejected",
                "detail": "AI Memory must not automatically rewrite trading rules",
                "rewrites_rules": False,
            }
        sanitized = dict(content)
        sanitized.pop("rewrite_rules", None)
        sanitized.pop("allow_order_send", None)
        sanitized.pop("bypass_risk", None)
        sanitized.pop("bypass_safety", None)
        allowed_kinds = {"observation", "report", "vote", "session"}
        record = MemoryRecord(
            memory_id=f"mem_{uuid4().hex[:12]}",
            kind=kind if kind in allowed_kinds else "observation",
            agent=agent,
            content=sanitized,
            session_id=session_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.max_memory:
                self._records = self._records[-self.max_memory :]
        return record

    def list(self, *, limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._records)
        if kind:
            rows = [r for r in rows if r.kind == kind]
        return [r.to_dict() for r in rows[-max(1, min(limit, self.max_memory)) :]]

    def status(self) -> dict[str, object]:
        with self._lock:
            count = len(self._records)
        return {
            "status": "available" if count else "empty",
            "count": count,
            "rewrite_attempts_blocked": self.rewrite_attempts,
            "allow_memory_rewrite_rules": False,
            "stores": ["observation", "report", "vote", "session"],
        }
