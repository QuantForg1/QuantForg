"""Postgres persistence for Execution Safety + Gateway."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.execution_gateway import ExecutionAttempt
from app.domain.entities.execution_safety import ExecutionDecisionRecord
from app.domain.enums.execution import ExecutionDecision, ExecutionOutcome
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


def _decision_from_row(row: Any) -> ExecutionDecisionRecord:
    created = parse_datetime(row["created_at"])
    return ExecutionDecisionRecord(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        decision=ExecutionDecision(str(row["decision"])),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        order_type=str(row["order_type"] or "market"),
        volume=parse_decimal(row["volume"]),
        rejection_reasons=[str(r) for r in json_list(row["rejection_reasons"])],
        warnings=[str(w) for w in json_list(row["warnings"])],
        calculated_risk=json_dict(row["calculated_risk"]),
        checks=_checks_from_row(row["checks"]),
        request_fingerprint=str(row["request_fingerprint"] or ""),
        request_snapshot=json_dict(row["request_snapshot"]),
        idempotent_replay=bool(row["idempotent_replay"]),
        decided_at=parse_datetime(row["decided_at"]),
        created_at=created,
        updated_at=created,
    )


def _attempt_from_row(row: Any) -> ExecutionAttempt:
    created = parse_datetime(row["created_at"])
    order_ticket = row["order_ticket"]
    deal_ticket = row["deal_ticket"]
    return ExecutionAttempt(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        order_type=str(row["order_type"] or "market"),
        volume=parse_decimal(row["volume"]),
        outcome=ExecutionOutcome(str(row["outcome"])),
        retcode=int(row["retcode"] or 0),
        message=str(row["message"] or ""),
        order_ticket=int(order_ticket) if order_ticket is not None else None,
        deal_ticket=int(deal_ticket) if deal_ticket is not None else None,
        price=parse_decimal(row["price"], "0"),
        retryable=bool(row["retryable"]),
        request_snapshot=json_dict(row["request_snapshot"]),
        result_snapshot=json_dict(row["result_snapshot"]),
        idempotent_replay=bool(row["idempotent_replay"]),
        submitted_at=parse_datetime(row["submitted_at"]),
        created_at=created,
        updated_at=created,
    )


class PostgresExecutionDecisionRepository:
    def __init__(self, uow: PostgresExecutionUnitOfWork) -> None:
        self._uow = uow

    async def add(self, decision: ExecutionDecisionRecord) -> ExecutionDecisionRecord:
        session = self._uow._require_session()
        params = {
            "id": str(decision.id),
            "user_id": str(decision.user_id),
            "request_id": decision.request_id,
            "decision": decision.decision.value,
            "symbol": decision.symbol,
            "side": decision.side,
            "order_type": decision.order_type,
            "volume": str(decision.volume),
            "rejection_reasons": as_json(decision.rejection_reasons),
            "warnings": as_json(decision.warnings),
            "calculated_risk": as_json(decision.calculated_risk),
            "checks": as_json(decision.checks),
            "request_fingerprint": decision.request_fingerprint,
            "request_snapshot": as_json(decision.request_snapshot),
            "idempotent_replay": decision.idempotent_replay,
            "decided_at": decision.decided_at,
            "created_at": decision.created_at,
        }
        insert_sql = """
            INSERT INTO execution_decisions (
                id, user_id, request_id, decision, symbol, side, order_type,
                volume, rejection_reasons, warnings, calculated_risk, checks,
                request_fingerprint, request_snapshot, idempotent_replay,
                decided_at, created_at
            ) VALUES (
                :id, :user_id, :request_id, :decision, :symbol, :side,
                :order_type, :volume, CAST(:rejection_reasons AS jsonb),
                CAST(:warnings AS jsonb), CAST(:calculated_risk AS jsonb),
                CAST(:checks AS jsonb), :request_fingerprint,
                CAST(:request_snapshot AS jsonb), :idempotent_replay,
                :decided_at, :created_at
            )
        """
        if decision.idempotent_replay:
            await session.execute(
                text(insert_sql + " ON CONFLICT (id) DO NOTHING"),
                params,
            )
        else:
            # Partial unique (user_id, request_id) WHERE NOT replay enforces
            # at most one canonical row; upsert by PK for same-entity re-add.
            await session.execute(
                text(insert_sql + """
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        request_id = EXCLUDED.request_id,
                        decision = EXCLUDED.decision,
                        symbol = EXCLUDED.symbol,
                        side = EXCLUDED.side,
                        order_type = EXCLUDED.order_type,
                        volume = EXCLUDED.volume,
                        rejection_reasons = EXCLUDED.rejection_reasons,
                        warnings = EXCLUDED.warnings,
                        calculated_risk = EXCLUDED.calculated_risk,
                        checks = EXCLUDED.checks,
                        request_fingerprint = EXCLUDED.request_fingerprint,
                        request_snapshot = EXCLUDED.request_snapshot,
                        idempotent_replay = EXCLUDED.idempotent_replay,
                        decided_at = EXCLUDED.decided_at
                    """),
                params,
            )
        return decision

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> ExecutionDecisionRecord | None:
        session = self._uow._require_session()
        key = request_id.strip()
        result = await session.execute(
            text("""
                SELECT * FROM execution_decisions
                WHERE user_id = :user_id AND request_id = :request_id
                  AND idempotent_replay = false
                ORDER BY decided_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id), "request_id": key},
        )
        row = result.mappings().first()
        if row:
            return _decision_from_row(row)
        result = await session.execute(
            text("""
                SELECT * FROM execution_decisions
                WHERE user_id = :user_id AND request_id = :request_id
                ORDER BY decided_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id), "request_id": key},
        )
        row = result.mappings().first()
        return _decision_from_row(row) if row else None

    async def list_recent_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[ExecutionDecisionRecord]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM execution_decisions
                WHERE user_id = :user_id
                ORDER BY decided_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_decision_from_row(r) for r in result.mappings().all()]


class PostgresExecutionAttemptRepository:
    def __init__(self, uow: PostgresExecutionUnitOfWork) -> None:
        self._uow = uow

    async def add(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        session = self._uow._require_session()
        params = {
            "id": str(attempt.id),
            "user_id": str(attempt.user_id),
            "request_id": attempt.request_id,
            "symbol": attempt.symbol,
            "side": attempt.side,
            "order_type": attempt.order_type,
            "volume": str(attempt.volume),
            "outcome": attempt.outcome.value,
            "retcode": attempt.retcode,
            "message": attempt.message,
            "order_ticket": attempt.order_ticket,
            "deal_ticket": attempt.deal_ticket,
            "price": str(attempt.price),
            "retryable": attempt.retryable,
            "request_snapshot": as_json(attempt.request_snapshot),
            "result_snapshot": as_json(attempt.result_snapshot),
            "idempotent_replay": attempt.idempotent_replay,
            "submitted_at": attempt.submitted_at,
            "created_at": attempt.created_at,
        }
        insert_cols = """
            INSERT INTO execution_attempts (
                id, user_id, request_id, symbol, side, order_type, volume,
                outcome, retcode, message, order_ticket, deal_ticket, price,
                retryable, request_snapshot, result_snapshot, idempotent_replay,
                submitted_at, created_at
            ) VALUES (
                :id, :user_id, :request_id, :symbol, :side, :order_type, :volume,
                :outcome, :retcode, :message, :order_ticket, :deal_ticket, :price,
                :retryable, CAST(:request_snapshot AS jsonb),
                CAST(:result_snapshot AS jsonb), :idempotent_replay,
                :submitted_at, :created_at
            )
        """
        update_set = """
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                request_id = EXCLUDED.request_id,
                symbol = EXCLUDED.symbol,
                side = EXCLUDED.side,
                order_type = EXCLUDED.order_type,
                volume = EXCLUDED.volume,
                outcome = EXCLUDED.outcome,
                retcode = EXCLUDED.retcode,
                message = EXCLUDED.message,
                order_ticket = EXCLUDED.order_ticket,
                deal_ticket = EXCLUDED.deal_ticket,
                price = EXCLUDED.price,
                retryable = EXCLUDED.retryable,
                request_snapshot = EXCLUDED.request_snapshot,
                result_snapshot = EXCLUDED.result_snapshot,
                idempotent_replay = EXCLUDED.idempotent_replay,
                submitted_at = EXCLUDED.submitted_at
        """
        if attempt.idempotent_replay:
            await session.execute(
                text(insert_cols + " ON CONFLICT (id) DO NOTHING"),
                params,
            )
        else:
            await session.execute(text(insert_cols + update_set), params)
        return attempt

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> ExecutionAttempt | None:
        session = self._uow._require_session()
        key = request_id.strip()
        result = await session.execute(
            text("""
                SELECT * FROM execution_attempts
                WHERE user_id = :user_id AND request_id = :request_id
                  AND idempotent_replay = false
                ORDER BY submitted_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id), "request_id": key},
        )
        row = result.mappings().first()
        if row:
            return _attempt_from_row(row)
        result = await session.execute(
            text("""
                SELECT * FROM execution_attempts
                WHERE user_id = :user_id AND request_id = :request_id
                ORDER BY submitted_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id), "request_id": key},
        )
        row = result.mappings().first()
        return _attempt_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAttempt]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM execution_attempts
                WHERE user_id = :user_id
                ORDER BY submitted_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_attempt_from_row(r) for r in result.mappings().all()]


class PostgresExecutionUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.decisions = PostgresExecutionDecisionRepository(self)
        self.attempts = PostgresExecutionAttemptRepository(self)


class PostgresExecutionUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresExecutionUnitOfWork:
        return PostgresExecutionUnitOfWork(self._database)
