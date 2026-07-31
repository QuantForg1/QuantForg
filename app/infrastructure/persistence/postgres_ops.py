"""Postgres persistence for Operations & Observability."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.ops import HealthHistoryEntry, SystemAlert, SystemMetricRecord
from app.domain.enums.ops import (
    AlertSeverity,
    AlertStatus,
    ComponentHealthStatus,
    ComponentKind,
)
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_datetime_optional,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _alert_from_row(row: Any) -> SystemAlert:
    return SystemAlert(
        id=parse_uuid(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        severity=AlertSeverity(str(row["severity"])),
        status=AlertStatus(str(row["status"])),
        component=ComponentKind(str(row["component"])),
        message=str(row["message"] or ""),
        details=json_dict(row["details"]),
        triggered_at=parse_datetime(row["triggered_at"]),
        resolved_at=parse_datetime_optional(row["resolved_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _metric_from_row(row: Any) -> SystemMetricRecord:
    return SystemMetricRecord(
        id=parse_uuid(row["id"]),
        payload=json_dict(row["payload"]),
        recorded_at=parse_datetime(row["recorded_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _health_from_row(row: Any) -> HealthHistoryEntry:
    return HealthHistoryEntry(
        id=parse_uuid(row["id"]),
        overall=ComponentHealthStatus(str(row["overall"])),
        payload=json_dict(row["payload"]),
        recorded_at=parse_datetime(row["recorded_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class PostgresSystemAlertRepository:
    def __init__(self, uow: PostgresOpsUnitOfWork) -> None:
        self._uow = uow

    async def add(self, alert: SystemAlert) -> SystemAlert:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO system_alerts (
                    id, code, name, severity, status, component, message, details,
                    triggered_at, resolved_at, created_at, updated_at
                ) VALUES (
                    :id, :code, :name, :severity, :status, :component, :message,
                    CAST(:details AS jsonb), :triggered_at, :resolved_at,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    code = EXCLUDED.code,
                    name = EXCLUDED.name,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    component = EXCLUDED.component,
                    message = EXCLUDED.message,
                    details = EXCLUDED.details,
                    triggered_at = EXCLUDED.triggered_at,
                    resolved_at = EXCLUDED.resolved_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(alert.id),
                "code": alert.code,
                "name": alert.name,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "component": alert.component.value,
                "message": alert.message,
                "details": as_json(alert.details),
                "triggered_at": alert.triggered_at,
                "resolved_at": alert.resolved_at,
                "created_at": alert.created_at,
                "updated_at": alert.updated_at,
            },
        )
        return alert

    async def get(self, alert_id: object) -> SystemAlert | None:
        if not isinstance(alert_id, UUID):
            return None
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM system_alerts WHERE id = :id"),
            {"id": str(alert_id)},
        )
        row = result.mappings().first()
        return _alert_from_row(row) if row else None

    async def list_open(self, *, limit: int = 100) -> list[SystemAlert]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM system_alerts
                WHERE status IN ('open', 'acknowledged')
                ORDER BY triggered_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_alert_from_row(r) for r in result.mappings().all()]

    async def list_recent(self, *, limit: int = 100) -> list[SystemAlert]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM system_alerts
                ORDER BY triggered_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_alert_from_row(r) for r in result.mappings().all()]

    async def update(self, alert: SystemAlert) -> SystemAlert:
        return await self.add(alert)

    async def find_open_by_code(self, code: str) -> SystemAlert | None:
        key = code.strip().lower()
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM system_alerts
                WHERE code = :code AND status IN ('open', 'acknowledged')
                ORDER BY triggered_at DESC
                LIMIT 1
                """
            ),
            {"code": key},
        )
        row = result.mappings().first()
        return _alert_from_row(row) if row else None


class PostgresSystemMetricRepository:
    def __init__(self, uow: PostgresOpsUnitOfWork) -> None:
        self._uow = uow

    async def add(self, record: SystemMetricRecord) -> SystemMetricRecord:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO system_metrics (
                    id, payload, recorded_at, created_at, updated_at
                )
                VALUES (
                    :id, CAST(:payload AS jsonb), :recorded_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    recorded_at = EXCLUDED.recorded_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(record.id),
                "payload": as_json(record.payload),
                "recorded_at": record.recorded_at,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            },
        )
        return record

    async def list_recent(self, *, limit: int = 100) -> list[SystemMetricRecord]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM system_metrics
                ORDER BY recorded_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_metric_from_row(r) for r in result.mappings().all()]


class PostgresHealthHistoryRepository:
    def __init__(self, uow: PostgresOpsUnitOfWork) -> None:
        self._uow = uow

    async def add(self, entry: HealthHistoryEntry) -> HealthHistoryEntry:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO health_history (
                    id, overall, payload, recorded_at, created_at, updated_at
                ) VALUES (
                    :id, :overall, CAST(:payload AS jsonb),
                    :recorded_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    overall = EXCLUDED.overall,
                    payload = EXCLUDED.payload,
                    recorded_at = EXCLUDED.recorded_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(entry.id),
                "overall": entry.overall.value,
                "payload": as_json(entry.payload),
                "recorded_at": entry.recorded_at,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            },
        )
        return entry

    async def list_recent(self, *, limit: int = 100) -> list[HealthHistoryEntry]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM health_history
                ORDER BY recorded_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_health_from_row(r) for r in result.mappings().all()]


class PostgresOpsUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.alerts = PostgresSystemAlertRepository(self)
        self.metrics = PostgresSystemMetricRepository(self)
        self.health_history = PostgresHealthHistoryRepository(self)


class PostgresOpsUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresOpsUnitOfWork:
        return PostgresOpsUnitOfWork(self._database)
