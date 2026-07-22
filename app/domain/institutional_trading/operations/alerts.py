"""Operator alerts — must be acknowledged. Group duplicates; reduce fatigue."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from app.domain.institutional_trading.operations.models import (
    AlertKind,
    AlertSeverity,
    OpsAlert,
)

# Info/warning kinds stay quiet for this window unless severity escalates.
_DEFAULT_COOLDOWN = timedelta(minutes=15)
_ESCALATE_AFTER = 3  # occurrences before bumping severity for grouping display


@dataclass
class AlertService:
    _alerts: list[OpsAlert] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_alerts: int = 5_000
    cooldown: timedelta = _DEFAULT_COOLDOWN

    def raise_alert(
        self,
        *,
        kind: AlertKind,
        severity: AlertSeverity,
        message: str,
        now: datetime | None = None,
        dedupe: bool = True,
    ) -> OpsAlert:
        """Raise an alert. Unacked same-kind alerts are grouped, not flooded."""
        moment = now or datetime.now(UTC)
        with self._lock:
            if dedupe:
                for i, existing in enumerate(reversed(self._alerts)):
                    if existing.acknowledged or existing.kind != kind:
                        continue
                    # Cooldown: suppress fresh duplicate unless severity rises
                    last = existing.last_seen_at or existing.created_at
                    severity_rank = {
                        AlertSeverity.INFO: 0,
                        AlertSeverity.WARNING: 1,
                        AlertSeverity.CRITICAL: 2,
                    }
                    escalates = (
                        severity_rank[severity]
                        > severity_rank[existing.severity]
                    )
                    within = moment - last <= self.cooldown
                    if within and not escalates:
                        count = existing.occurrence_count + 1
                        new_sev = existing.severity
                        if (
                            count >= _ESCALATE_AFTER
                            and existing.severity != AlertSeverity.CRITICAL
                            and existing.severity != AlertSeverity.INFO
                        ):
                            # Meaningful incident: escalate warning → critical
                            # after repeated hits within cooldown window.
                            new_sev = AlertSeverity.CRITICAL
                        updated = replace(
                            existing,
                            occurrence_count=count,
                            last_seen_at=moment,
                            severity=new_sev,
                            message=message or existing.message,
                        )
                        # reversed index → actual index
                        idx = len(self._alerts) - 1 - i
                        self._alerts[idx] = updated
                        return updated
                    if not within:
                        break
            alert = OpsAlert(
                kind=kind,
                severity=severity,
                message=message,
                created_at=moment,
                last_seen_at=moment,
                occurrence_count=1,
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
                        occurrence_count=a.occurrence_count,
                        last_seen_at=a.last_seen_at,
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

    def grouped(self, *, unacked_only: bool = True) -> list[dict[str, object]]:
        """Group by kind for operator desks — reduces alert fatigue."""
        rows = self.list(limit=5_000, unacked_only=unacked_only)
        by_kind: dict[str, list[OpsAlert]] = {}
        for a in rows:
            by_kind.setdefault(a.kind.value, []).append(a)
        out: list[dict[str, object]] = []
        for kind, items in by_kind.items():
            latest = max(items, key=lambda x: x.last_seen_at or x.created_at)
            out.append(
                {
                    "kind": kind,
                    "count": sum(i.occurrence_count for i in items),
                    "severity": latest.severity.value,
                    "message": latest.message,
                    "latest_id": str(latest.id),
                    "last_seen_at": (
                        (latest.last_seen_at or latest.created_at).isoformat()
                    ),
                    "escalate": latest.severity == AlertSeverity.CRITICAL
                    or sum(i.occurrence_count for i in items) >= _ESCALATE_AFTER,
                }
            )
        out.sort(key=lambda r: str(r["last_seen_at"]), reverse=True)
        return out

    def unacked_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._alerts if not a.acknowledged)
