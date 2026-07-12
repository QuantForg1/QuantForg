"""Operations & Observability domain models — operational only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.ops import (
    AlertSeverity,
    AlertStatus,
    ComponentHealthStatus,
    ComponentKind,
)


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """Health of one monitored component."""

    kind: ComponentKind
    status: ComponentHealthStatus
    detail: str = ""
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "status": self.status.value,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class MonitoringDashboard:
    """Aggregated monitoring dashboard snapshot."""

    overall: ComponentHealthStatus
    components: tuple[ComponentHealth, ...]
    collected_at: datetime
    execution_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall.value,
            "components": [c.to_dict() for c in self.components],
            "collected_at": self.collected_at.isoformat(),
            "execution_enabled": self.execution_enabled,
        }


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Collected operational metrics."""

    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    throughput_per_minute: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_ratio: float = 0.0
    job_count: int = 0
    avg_job_duration_ms: float = 0.0
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "request_latency_ms_avg": round(self.avg_latency_ms, 3),
            "error_rate": round(self.error_rate, 6),
            "throughput_per_minute": round(self.throughput_per_minute, 3),
            "cache_hit_ratio": round(self.cache_hit_ratio, 6),
            "job_duration_ms_avg": round(self.avg_job_duration_ms, 3),
            "request_count": self.request_count,
            "error_count": self.error_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "job_count": self.job_count,
            "collected_at": self.collected_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AlertRule:
    """Declarative alert rule evaluated against monitoring state."""

    code: str
    name: str
    severity: AlertSeverity
    component: ComponentKind
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "severity": self.severity.value,
            "component": self.component.value,
            "description": self.description,
        }


@dataclass(eq=False, kw_only=True)
class SystemAlert(Entity):
    """Persisted operational alert."""

    code: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    component: ComponentKind
    message: str
    details: dict[str, object] = field(default_factory=dict)
    triggered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        self.code = self.code.strip().lower()
        self.name = self.name.strip()
        self.message = self.message.strip()[:1000]
        require(len(self.code) > 0, "code is required")
        require(len(self.name) > 0, "name is required")

    @classmethod
    def open_alert(
        cls,
        *,
        code: str,
        name: str,
        severity: AlertSeverity,
        component: ComponentKind,
        message: str,
        details: dict[str, object] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "code": code,
            "name": name,
            "severity": severity,
            "status": AlertStatus.OPEN,
            "component": component,
            "message": message,
            "details": dict(details or {}),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def acknowledge(self) -> None:
        require(self.status is AlertStatus.OPEN, "only open alerts can be acknowledged")
        self.status = AlertStatus.ACKNOWLEDGED
        self.touch()

    def resolve(self, *, at: datetime | None = None) -> None:
        require(
            self.status in {AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED},
            "alert cannot be resolved in current status",
        )
        self.status = AlertStatus.RESOLVED
        self.resolved_at = at or datetime.now(UTC)
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "code": self.code,
                "name": self.name,
                "severity": self.severity.value,
                "status": self.status.value,
                "component": self.component.value,
                "message": self.message,
                "details": dict(self.details),
                "triggered_at": self.triggered_at.isoformat(),
                "resolved_at": (
                    self.resolved_at.isoformat() if self.resolved_at else None
                ),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class HealthHistoryEntry(Entity):
    """Point-in-time health snapshot for history."""

    overall: ComponentHealthStatus
    payload: dict[str, object] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "overall": self.overall.value,
                "payload": dict(self.payload),
                "recorded_at": self.recorded_at.isoformat(),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class SystemMetricRecord(Entity):
    """Persisted metrics snapshot row."""

    payload: dict[str, object] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "payload": dict(self.payload),
                "recorded_at": self.recorded_at.isoformat(),
            }
        )
        return base
