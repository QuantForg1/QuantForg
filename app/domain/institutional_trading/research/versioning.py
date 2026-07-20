"""Strategy versioning — append-only simulation results; never overwrite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.research.models import SimulationResult


@dataclass
class StrategyVersionStore:
    """In-process append-only research result store.

    DB schema documented separately.
    """

    _rows: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def append(
        self, result: SimulationResult, *, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        row = {
            "stored_at": datetime.now(UTC).isoformat(),
            "run_id": str(result.run_id),
            "strategy_version": result.strategy_version,
            "config_version": result.config_version,
            "input_hash": result.input_hash,
            "git_commit": result.git_commit,
            "metrics": result.analytics.to_dict(),
            "bars_processed": result.bars_processed,
            "trade_count": result.analytics.trade_count,
            "meta": dict(meta or {}),
        }
        with self._lock:
            self._rows.append(row)
            return dict(row)

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._rows[-limit:])

    def by_run_id(self, run_id: UUID | str) -> dict[str, Any] | None:
        rid = str(run_id)
        with self._lock:
            for row in reversed(self._rows):
                if row["run_id"] == rid:
                    return dict(row)
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._rows)
