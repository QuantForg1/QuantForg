"""Postgres persistence for Strategy Runtime."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.domain.entities.strategy_runtime import StrategyEvaluation, StrategySignal
from app.domain.enums.signal import SignalDirection
from app.domain.enums.strategy import StrategyDecisionType
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    json_list,
    parse_datetime,
    parse_uuid,
    parse_uuid_optional,
)
from core.database.session import DatabaseManager


def _preconditions_from_row(value: object) -> dict[str, bool]:
    return {str(k): bool(v) for k, v in json_dict(value).items()}


def _evaluation_from_row(row: Any) -> StrategyEvaluation:
    created = parse_datetime(row["created_at"])
    risk_score = row["risk_score"]
    return StrategyEvaluation(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"] or "m15"),
        decision=StrategyDecisionType(str(row["decision"])),
        reasons=[str(r) for r in json_list(row["reasons"])],
        preconditions=_preconditions_from_row(row["preconditions"]),
        market_state=json_dict(row["market_state"]),
        signal_id=parse_uuid_optional(row["signal_id"]),
        risk_decision=(
            str(row["risk_decision"]) if row["risk_decision"] is not None else None
        ),
        risk_score=int(risk_score) if risk_score is not None else None,
        evaluated_at=parse_datetime(row["evaluated_at"]),
        created_at=created,
        updated_at=created,
    )


def _signal_from_row(row: Any) -> StrategySignal:
    created = parse_datetime(row["created_at"])
    return StrategySignal(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"] or "m15"),
        direction=SignalDirection(str(row["direction"])),
        confidence=float(row["confidence"]),
        reasons=[str(r) for r in json_list(row["reasons"])],
        generated_at=parse_datetime(row["generated_at"]),
        evaluation_id=parse_uuid_optional(row["evaluation_id"]),
        rejected=bool(row["rejected"]),
        rejection_reasons=[str(r) for r in json_list(row["rejection_reasons"])],
        created_at=created,
        updated_at=created,
    )


class PostgresStrategyEvaluationRepository:
    def __init__(self, uow: PostgresStrategyUnitOfWork) -> None:
        self._uow = uow

    async def add(self, evaluation: StrategyEvaluation) -> StrategyEvaluation:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO strategy_evaluations (
                    id, user_id, request_id, symbol, timeframe, decision, reasons,
                    preconditions, market_state, signal_id, risk_decision,
                    risk_score, evaluated_at, created_at
                ) VALUES (
                    :id, :user_id, :request_id, :symbol, :timeframe, :decision,
                    CAST(:reasons AS jsonb), CAST(:preconditions AS jsonb),
                    CAST(:market_state AS jsonb), :signal_id, :risk_decision,
                    :risk_score, :evaluated_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    request_id = EXCLUDED.request_id,
                    symbol = EXCLUDED.symbol,
                    timeframe = EXCLUDED.timeframe,
                    decision = EXCLUDED.decision,
                    reasons = EXCLUDED.reasons,
                    preconditions = EXCLUDED.preconditions,
                    market_state = EXCLUDED.market_state,
                    signal_id = EXCLUDED.signal_id,
                    risk_decision = EXCLUDED.risk_decision,
                    risk_score = EXCLUDED.risk_score,
                    evaluated_at = EXCLUDED.evaluated_at
                """
            ),
            {
                "id": str(evaluation.id),
                "user_id": str(evaluation.user_id),
                "request_id": evaluation.request_id,
                "symbol": evaluation.symbol,
                "timeframe": evaluation.timeframe,
                "decision": evaluation.decision.value,
                "reasons": as_json(evaluation.reasons),
                "preconditions": as_json(evaluation.preconditions),
                "market_state": as_json(evaluation.market_state),
                "signal_id": (
                    str(evaluation.signal_id) if evaluation.signal_id else None
                ),
                "risk_decision": evaluation.risk_decision,
                "risk_score": evaluation.risk_score,
                "evaluated_at": evaluation.evaluated_at,
                "created_at": evaluation.created_at,
            },
        )
        return evaluation

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> StrategyEvaluation | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM strategy_evaluations
                WHERE user_id = :user_id AND request_id = :request_id
                ORDER BY evaluated_at DESC
                LIMIT 1
                """
            ),
            {"user_id": str(user_id), "request_id": request_id.strip()},
        )
        row = result.mappings().first()
        return _evaluation_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[StrategyEvaluation]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM strategy_evaluations
                WHERE user_id = :user_id
                ORDER BY evaluated_at DESC
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_evaluation_from_row(r) for r in result.mappings().all()]


class PostgresStrategySignalRepository:
    def __init__(self, uow: PostgresStrategyUnitOfWork) -> None:
        self._uow = uow

    async def add(self, signal: StrategySignal) -> StrategySignal:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO strategy_signals (
                    id, user_id, evaluation_id, symbol, timeframe, direction,
                    confidence, reasons, rejected, rejection_reasons,
                    generated_at, created_at
                ) VALUES (
                    :id, :user_id, :evaluation_id, :symbol, :timeframe, :direction,
                    :confidence, CAST(:reasons AS jsonb), :rejected,
                    CAST(:rejection_reasons AS jsonb), :generated_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    evaluation_id = EXCLUDED.evaluation_id,
                    symbol = EXCLUDED.symbol,
                    timeframe = EXCLUDED.timeframe,
                    direction = EXCLUDED.direction,
                    confidence = EXCLUDED.confidence,
                    reasons = EXCLUDED.reasons,
                    rejected = EXCLUDED.rejected,
                    rejection_reasons = EXCLUDED.rejection_reasons,
                    generated_at = EXCLUDED.generated_at
                """
            ),
            {
                "id": str(signal.id),
                "user_id": str(signal.user_id),
                "evaluation_id": (
                    str(signal.evaluation_id) if signal.evaluation_id else None
                ),
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "direction": signal.direction.value,
                "confidence": signal.confidence,
                "reasons": as_json(signal.reasons),
                "rejected": signal.rejected,
                "rejection_reasons": as_json(signal.rejection_reasons),
                "generated_at": signal.generated_at,
                "created_at": signal.created_at,
            },
        )
        return signal

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, include_rejected: bool = True
    ) -> list[StrategySignal]:
        session = self._uow._require_session()
        if include_rejected:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM strategy_signals
                    WHERE user_id = :user_id
                    ORDER BY generated_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": str(user_id), "limit": limit},
            )
        else:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM strategy_signals
                    WHERE user_id = :user_id AND rejected = false
                    ORDER BY generated_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": str(user_id), "limit": limit},
            )
        return [_signal_from_row(r) for r in result.mappings().all()]


class PostgresStrategyDecisionHistoryRepository:
    def __init__(self, uow: PostgresStrategyUnitOfWork) -> None:
        self._uow = uow

    async def add(
        self,
        *,
        user_id: UUID,
        evaluation_id: UUID,
        decision: str,
        reasons: list[str],
    ) -> None:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO strategy_decision_history (
                    id, user_id, evaluation_id, decision, reasons
                ) VALUES (
                    :id, :user_id, :evaluation_id, :decision,
                    CAST(:reasons AS jsonb)
                )
                """
            ),
            {
                "id": str(uuid4()),
                "user_id": str(user_id),
                "evaluation_id": str(evaluation_id),
                "decision": decision,
                "reasons": as_json(list(reasons)),
            },
        )


class PostgresStrategyUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.evaluations = PostgresStrategyEvaluationRepository(self)
        self.signals = PostgresStrategySignalRepository(self)
        self.decision_history = PostgresStrategyDecisionHistoryRepository(self)


class PostgresStrategyUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresStrategyUnitOfWork:
        return PostgresStrategyUnitOfWork(self._database)
