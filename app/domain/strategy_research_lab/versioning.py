"""Version History — lab strategy versions (no live deployment)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    version_id: str
    strategy_key: str
    version: str
    parameters: dict[str, Any]
    notes: str
    created_at: datetime
    created_by: str

    def to_dict(self) -> dict[str, object]:
        return {
            "version_id": self.version_id,
            "strategy_key": self.strategy_key,
            "version": self.version,
            "parameters": dict(self.parameters),
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "lab_only": True,
            "deployed_to_production": False,
        }


@dataclass
class VersionHistoryStore:
    _versions: dict[str, list[StrategyVersion]] = field(default_factory=dict)

    def record(
        self,
        *,
        strategy_key: str,
        version: str,
        parameters: dict[str, Any] | None = None,
        notes: str = "",
        created_by: str = "operator",
    ) -> dict[str, object]:
        row = StrategyVersion(
            version_id=str(uuid4()),
            strategy_key=strategy_key,
            version=version,
            parameters=dict(parameters or {}),
            notes=notes,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
        bucket = self._versions.setdefault(strategy_key, [])
        bucket.append(row)
        if len(bucket) > 200:
            del bucket[:-150]
        return row.to_dict()

    def list_versions(
        self, strategy_key: str, *, limit: int = 50
    ) -> list[dict[str, object]]:
        rows = list(self._versions.get(strategy_key, []))
        return [r.to_dict() for r in reversed(rows[-limit:])]
