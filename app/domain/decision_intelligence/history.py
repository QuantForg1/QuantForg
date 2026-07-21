"""Auditable decision history + replay helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.decision_intelligence.config import DecisionIntelligenceConfig


@dataclass
class DecisionHistoryStore:
    config: DecisionIntelligenceConfig
    _rows: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(self, decision: dict[str, Any]) -> dict[str, Any]:
        row = {
            **deepcopy(decision),
            "audit_id": decision.get("audit_id") or str(uuid4()),
            "recorded_at": datetime.now(UTC).isoformat(),
            "auditable": True,
        }
        with self._lock:
            self._rows.append(row)
            if len(self._rows) > self.config.max_history:
                self._rows = self._rows[-self.config.max_history :]
        return deepcopy(row)

    def list_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._rows[-limit:])
        return list(reversed(deepcopy(rows)))

    def get(self, audit_id: str) -> dict[str, Any] | None:
        with self._lock:
            for row in reversed(self._rows):
                if row.get("audit_id") == audit_id:
                    return deepcopy(row)
        return None

    def replay(self, audit_id: str) -> dict[str, Any]:
        row = self.get(audit_id)
        if not row:
            return {
                "status": "unavailable",
                "reason": f"No auditable decision {audit_id}.",
                "replay": None,
            }
        return {
            "status": "available",
            "reason": "Replaying stored decision record (read-only).",
            "replay": row,
            "note": (
                "Decision replay does not place orders and does not "
                "re-submit to brokers."
            ),
        }
