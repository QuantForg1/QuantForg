"""Operations & Observability enumerations — operational only."""

from __future__ import annotations

from enum import StrEnum


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    """Lifecycle of an operational alert."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ComponentKind(StrEnum):
    """Monitored system components."""

    SYSTEM = "system"
    BROKER = "broker"
    MT5 = "mt5"
    API = "api"
    DATABASE = "database"
    QUEUE = "queue"
    BACKGROUND_JOBS = "background_jobs"


class ComponentHealthStatus(StrEnum):
    """Per-component health for the monitoring dashboard."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
