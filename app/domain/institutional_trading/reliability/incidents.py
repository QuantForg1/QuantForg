"""Incident manager — severity, escalation, lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from app.domain.institutional_trading.reliability.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)

# Escalation: minutes open before bumping level (deterministic thresholds)
ESCALATION_MINUTES: dict[IncidentSeverity, tuple[int, ...]] = {
    IncidentSeverity.INFO: (60,),
    IncidentSeverity.WARNING: (15, 45),
    IncidentSeverity.ERROR: (5, 15, 30),
    IncidentSeverity.CRITICAL: (1, 5, 10),
}


@dataclass
class IncidentManager:
    _incidents: list[Incident] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def open(
        self,
        *,
        severity: IncidentSeverity,
        title: str,
        detail: str,
        source: str,
        now: datetime | None = None,
    ) -> Incident:
        inc = Incident(
            severity=severity,
            title=title,
            detail=detail,
            source=source,
            created_at=now or datetime.now(UTC),
        )
        with self._lock:
            self._incidents.append(inc)
        return inc

    def acknowledge(
        self, incident_id: UUID, *, by: str, _now: datetime | None = None
    ) -> Incident | None:
        with self._lock:
            for i, inc in enumerate(self._incidents):
                if inc.id == incident_id:
                    updated = Incident(
                        severity=inc.severity,
                        title=inc.title,
                        detail=inc.detail,
                        source=inc.source,
                        created_at=inc.created_at,
                        status=IncidentStatus.ACKNOWLEDGED,
                        escalation_level=inc.escalation_level,
                        id=inc.id,
                        resolved_at=inc.resolved_at,
                        acknowledged_by=by,
                    )
                    self._incidents[i] = updated
                    return updated
        return None

    def resolve(
        self, incident_id: UUID, *, now: datetime | None = None
    ) -> Incident | None:
        moment = now or datetime.now(UTC)
        with self._lock:
            for i, inc in enumerate(self._incidents):
                if inc.id == incident_id:
                    updated = Incident(
                        severity=inc.severity,
                        title=inc.title,
                        detail=inc.detail,
                        source=inc.source,
                        created_at=inc.created_at,
                        status=IncidentStatus.RESOLVED,
                        escalation_level=inc.escalation_level,
                        id=inc.id,
                        resolved_at=moment,
                        acknowledged_by=inc.acknowledged_by,
                    )
                    self._incidents[i] = updated
                    return updated
        return None

    def apply_escalation(self, *, now: datetime | None = None) -> list[Incident]:
        """Bump escalation_level for open incidents past thresholds."""
        moment = now or datetime.now(UTC)
        bumped: list[Incident] = []
        with self._lock:
            for i, inc in enumerate(self._incidents):
                if inc.status is IncidentStatus.RESOLVED:
                    continue
                age_min = (moment - inc.created_at).total_seconds() / 60.0
                thresholds = ESCALATION_MINUTES.get(inc.severity, ())
                level = 0
                for t in thresholds:
                    if age_min >= t:
                        level += 1
                if level > inc.escalation_level:
                    updated = Incident(
                        severity=inc.severity,
                        title=inc.title,
                        detail=inc.detail,
                        source=inc.source,
                        created_at=inc.created_at,
                        status=(
                            IncidentStatus.MITIGATING
                            if inc.status is not IncidentStatus.ACKNOWLEDGED
                            else inc.status
                        ),
                        escalation_level=level,
                        id=inc.id,
                        resolved_at=inc.resolved_at,
                        acknowledged_by=inc.acknowledged_by,
                    )
                    self._incidents[i] = updated
                    bumped.append(updated)
        return bumped

    def list(
        self,
        *,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        with self._lock:
            rows = list(self._incidents)
        if status:
            rows = [r for r in rows if r.status is status]
        if severity:
            rows = [r for r in rows if r.severity is severity]
        return rows[-limit:]

    def open_count(self) -> int:
        with self._lock:
            return sum(
                1 for i in self._incidents if i.status is not IncidentStatus.RESOLVED
            )
