"""Append-only configuration version store — never overwrite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.operations.models import (
    ConfigVersionRecord,
    OpsExecutionMode,
)


@dataclass
class ConfigVersionStore:
    _versions: list[ConfigVersionRecord] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _active_id: UUID | None = field(default=None, repr=False)

    def promote(
        self,
        *,
        config_version: str,
        strategy_version: str,
        operator: str,
        reason: str,
        risk_per_trade_pct: Decimal,
        max_daily_loss_pct: Decimal,
        max_open_trades: int,
        execution_mode: OpsExecutionMode,
        payload: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ConfigVersionRecord:
        with self._lock:
            rollback_target = (
                self._versions[-1].config_version if self._versions else None
            )
            record = ConfigVersionRecord(
                config_version=config_version,
                strategy_version=strategy_version,
                promoted_at=now or datetime.now(UTC),
                operator=operator,
                reason=reason,
                rollback_target=rollback_target,
                risk_per_trade_pct=risk_per_trade_pct,
                max_daily_loss_pct=max_daily_loss_pct,
                max_open_trades=max_open_trades,
                execution_mode=execution_mode,
                payload=dict(payload or {}),
            )
            self._versions.append(record)
            self._active_id = record.id
            return record

    def active(self) -> ConfigVersionRecord | None:
        with self._lock:
            if self._active_id is None:
                return self._versions[-1] if self._versions else None
            for v in reversed(self._versions):
                if v.id == self._active_id:
                    return v
            return self._versions[-1] if self._versions else None

    def get_by_config_version(self, config_version: str) -> ConfigVersionRecord | None:
        with self._lock:
            for v in reversed(self._versions):
                if v.config_version == config_version:
                    return v
        return None

    def rollback_to(self, config_version: str) -> ConfigVersionRecord | None:
        """Activate a previous config version (does not delete history)."""
        with self._lock:
            for v in reversed(self._versions):
                if v.config_version == config_version:
                    self._active_id = v.id
                    return v
        return None

    def list(self, *, limit: int = 100) -> list[ConfigVersionRecord]:
        with self._lock:
            return list(self._versions[-limit:])

    def count(self) -> int:
        with self._lock:
            return len(self._versions)
