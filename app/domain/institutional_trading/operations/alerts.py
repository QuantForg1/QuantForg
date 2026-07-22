"""Operator alerts — must be acknowledged."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from app.domain.institutional_trading.operations.models import (
    AlertKind,
    AlertSeverity,
    OpsAlert,
)


@dataclass
class AlertService:
    _alerts: list[OpsAlert] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_alerts: int = 5_000

    def raise_alert(
        self,
        *,
        kind: AlertKind,
        severity: AlertSeverity,
        message: str,
        now: datetime | None = None,
        dedupe: bool = True,
    ) -> OpsAlert:
        """Raise an alert. Unacked same-kind alerts are not duplicated by default."""
        with self._lock:
            if dedupe:
                for existing in reversed(self._alerts):
                    if (
                        not existing.acknowledged
                        and existing.kind == kind
                    ):
                        return existing
            alert = OpsAlert(
                kind=kind,
                severity=severity,
                message=message,
                created_at=now or datetime.now(UTC),
            )
            self._alerts.append(alert)
            if len(self._alerts) > self.max_alerts:
                self._alerts = self._alerts[-self.max_alerts :]
            return alert

    def acknowledge(
        self,
        alert_id: UUID,
        *,
        operator: str,
        now: datetime | None = None,
    ) -> OpsAlert | None:
        with self._lock:
            for i, a in enumerate(self._alerts):
                if a.id == alert_id:
                    updated = OpsAlert(
                        kind=a.kind,
                        severity=a.severity,
                        message=a.message,
                        created_at=a.created_at,
                        acknowledged=True,
                        acknowledged_by=operator,
                        acknowledged_at=now or datetime.now(UTC),
                        id=a.id,
                    )
                    self._alerts[i] = updated
                    return updated
        return None

    def list(self, *, limit: int = 100, unacked_only: bool = False) -> list[OpsAlert]:
        with self._lock:
            rows = list(self._alerts)
        if unacked_only:
            rows = [a for a in rows if not a.acknowledged]
        return rows[-limit:]

    def unacked_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._alerts if not a.acknowledged)
