"""Postgres persistence for Risk Management Engine assessments."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.risk_engine import RiskAssessment
from app.domain.enums.risk import RiskDecision, RiskScoreBand
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    json_list,
    parse_datetime,
    parse_decimal,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _checks_from_row(value: object) -> dict[str, bool]:
    return {str(k): bool(v) for k, v in json_dict(value).items()}


def _assessment_from_row(row: Any) -> RiskAssessment:
    created = parse_datetime(row["created_at"])
    return RiskAssessment(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        decision=RiskDecision(str(row["decision"])),
        risk_score=int(row["risk_score"]),
        risk_band=RiskScoreBand(str(row["risk_band"])),
        approved_lots=parse_decimal(row["approved_lots"]),
        requested_lots=parse_decimal(row["requested_lots"]),
        sizing_method=str(row["sizing_method"] or "percentage_risk"),
        warnings=[str(w) for w in json_list(row["warnings"])],
        reasons=[str(r) for r in json_list(row["reasons"])],
        exposure=json_dict(row["exposure"]),
        drawdown=json_dict(row["drawdown"]),
        checks=_checks_from_row(row["checks"]),
        request_snapshot=json_dict(row["request_snapshot"]),
        assessed_at=parse_datetime(row["assessed_at"]),
        created_at=created,
        updated_at=created,
    )


class PostgresRiskAssessmentRepository:
    def __init__(self, uow: PostgresRiskUnitOfWork) -> None:
        self._uow = uow

    async def add(self, assessment: RiskAssessment) -> RiskAssessment:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO risk_assessments (
                    id, user_id, request_id, symbol, side, decision, risk_score,
                    risk_band, approved_lots, requested_lots, sizing_method,
                    warnings, reasons, exposure, drawdown, checks,
                    request_snapshot, assessed_at, created_at
                ) VALUES (
                    :id, :user_id, :request_id, :symbol, :side, :decision,
                    :risk_score, :risk_band, :approved_lots, :requested_lots,
                    :sizing_method, CAST(:warnings AS jsonb), CAST(:reasons AS jsonb),
                    CAST(:exposure AS jsonb), CAST(:drawdown AS jsonb),
                    CAST(:checks AS jsonb), CAST(:request_snapshot AS jsonb),
                    :assessed_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    request_id = EXCLUDED.request_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    decision = EXCLUDED.decision,
                    risk_score = EXCLUDED.risk_score,
                    risk_band = EXCLUDED.risk_band,
                    approved_lots = EXCLUDED.approved_lots,
                    requested_lots = EXCLUDED.requested_lots,
                    sizing_method = EXCLUDED.sizing_method,
                    warnings = EXCLUDED.warnings,
                    reasons = EXCLUDED.reasons,
                    exposure = EXCLUDED.exposure,
                    drawdown = EXCLUDED.drawdown,
                    checks = EXCLUDED.checks,
                    request_snapshot = EXCLUDED.request_snapshot,
                    assessed_at = EXCLUDED.assessed_at
                """),
            {
                "id": str(assessment.id),
                "user_id": str(assessment.user_id),
                "request_id": assessment.request_id,
                "symbol": assessment.symbol,
                "side": assessment.side,
                "decision": assessment.decision.value,
                "risk_score": assessment.risk_score,
                "risk_band": assessment.risk_band.value,
                "approved_lots": str(assessment.approved_lots),
                "requested_lots": str(assessment.requested_lots),
                "sizing_method": assessment.sizing_method,
                "warnings": as_json(assessment.warnings),
                "reasons": as_json(assessment.reasons),
                "exposure": as_json(assessment.exposure),
                "drawdown": as_json(assessment.drawdown),
                "checks": as_json(assessment.checks),
                "request_snapshot": as_json(assessment.request_snapshot),
                "assessed_at": assessment.assessed_at,
                "created_at": assessment.created_at,
            },
        )
        return assessment

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> RiskAssessment | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM risk_assessments
                WHERE user_id = :user_id AND request_id = :request_id
                ORDER BY assessed_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id), "request_id": request_id.strip()},
        )
        row = result.mappings().first()
        return _assessment_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[RiskAssessment]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM risk_assessments
                WHERE user_id = :user_id
                ORDER BY assessed_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_assessment_from_row(r) for r in result.mappings().all()]


class PostgresRiskUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.assessments = PostgresRiskAssessmentRepository(self)


class PostgresRiskUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresRiskUnitOfWork:
        return PostgresRiskUnitOfWork(self._database)
