"""Postgres persistence for Walk-Forward Validation Engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.domain.entities.walkforward import WalkForwardRun
from app.domain.enums.walkforward import PromotionDecision, WalkForwardStatus
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    json_list,
    parse_datetime,
    parse_datetime_optional,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _run_from_row(row: Any) -> WalkForwardRun:
    promotion = row["promotion"]
    return WalkForwardRun(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"] or "m15"),
        status=WalkForwardStatus(str(row["status"])),
        promotion=PromotionDecision(str(promotion)) if promotion else None,
        window_config=json_dict(row["window_config"]),
        folds=[dict(f) if isinstance(f, dict) else {} for f in json_list(row["folds"])],
        aggregated_is=json_dict(row["aggregated_is"]),
        aggregated_oos=json_dict(row["aggregated_oos"]),
        robustness=json_dict(row["robustness"]),
        combined_equity=[
            dict(p) if isinstance(p, dict) else {}
            for p in json_list(row["combined_equity"])
        ],
        report=json_dict(row["report"]),
        bar_count=int(row["bar_count"] or 0),
        fold_count=int(row["fold_count"] or 0),
        error_message=str(row["error_message"] or ""),
        started_at=parse_datetime_optional(row["started_at"]),
        finished_at=parse_datetime_optional(row["finished_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class PostgresWalkForwardRunRepository:
    def __init__(self, uow: PostgresWalkForwardUnitOfWork) -> None:
        self._uow = uow

    async def add(self, run: WalkForwardRun) -> WalkForwardRun:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO walkforward_runs (
                    id, user_id, request_id, symbol, timeframe, status, promotion,
                    window_config, folds, aggregated_is, aggregated_oos, robustness,
                    combined_equity, report, bar_count, fold_count, error_message,
                    started_at, finished_at, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :request_id, :symbol, :timeframe, :status,
                    :promotion, CAST(:window_config AS jsonb), CAST(:folds AS jsonb),
                    CAST(:aggregated_is AS jsonb), CAST(:aggregated_oos AS jsonb),
                    CAST(:robustness AS jsonb), CAST(:combined_equity AS jsonb),
                    CAST(:report AS jsonb), :bar_count, :fold_count, :error_message,
                    :started_at, :finished_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    request_id = EXCLUDED.request_id,
                    symbol = EXCLUDED.symbol,
                    timeframe = EXCLUDED.timeframe,
                    status = EXCLUDED.status,
                    promotion = EXCLUDED.promotion,
                    window_config = EXCLUDED.window_config,
                    folds = EXCLUDED.folds,
                    aggregated_is = EXCLUDED.aggregated_is,
                    aggregated_oos = EXCLUDED.aggregated_oos,
                    robustness = EXCLUDED.robustness,
                    combined_equity = EXCLUDED.combined_equity,
                    report = EXCLUDED.report,
                    bar_count = EXCLUDED.bar_count,
                    fold_count = EXCLUDED.fold_count,
                    error_message = EXCLUDED.error_message,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    updated_at = EXCLUDED.updated_at
                """),
            {
                "id": str(run.id),
                "user_id": str(run.user_id),
                "request_id": run.request_id,
                "symbol": run.symbol,
                "timeframe": run.timeframe,
                "status": run.status.value,
                "promotion": run.promotion.value if run.promotion else None,
                "window_config": as_json(run.window_config),
                "folds": as_json(run.folds),
                "aggregated_is": as_json(run.aggregated_is),
                "aggregated_oos": as_json(run.aggregated_oos),
                "robustness": as_json(run.robustness),
                "combined_equity": as_json(run.combined_equity),
                "report": as_json(run.report),
                "bar_count": run.bar_count,
                "fold_count": run.fold_count,
                "error_message": run.error_message,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
            },
        )
        return run

    async def get(self, run_id: UUID) -> WalkForwardRun | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM walkforward_runs WHERE id = :id"),
            {"id": str(run_id)},
        )
        row = result.mappings().first()
        return _run_from_row(row) if row else None

    async def get_for_user(self, user_id: UUID, run_id: UUID) -> WalkForwardRun | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM walkforward_runs
                WHERE id = :id AND user_id = :user_id
                """),
            {"id": str(run_id), "user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _run_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[WalkForwardRun]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM walkforward_runs
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_run_from_row(r) for r in result.mappings().all()]


class PostgresWalkForwardUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.runs = PostgresWalkForwardRunRepository(self)
        self.oos_metrics: list[dict[str, object]] = []
        self.robustness_reports: list[dict[str, object]] = []

    async def add_oos_metrics(
        self, *, user_id: UUID, run_id: UUID, payload: dict[str, object]
    ) -> None:
        entry = {"user_id": user_id, "run_id": run_id, "payload": dict(payload)}
        self.oos_metrics.append(entry)
        session = self._require_session()
        await session.execute(
            text("""
                INSERT INTO walkforward_oos_metrics (
                    id, walkforward_id, user_id, payload
                ) VALUES (
                    :id, :walkforward_id, :user_id, CAST(:payload AS jsonb)
                )
                """),
            {
                "id": str(uuid4()),
                "walkforward_id": str(run_id),
                "user_id": str(user_id),
                "payload": as_json(payload),
            },
        )

    async def add_robustness_report(
        self, *, user_id: UUID, run_id: UUID, payload: dict[str, object]
    ) -> None:
        entry = {"user_id": user_id, "run_id": run_id, "payload": dict(payload)}
        self.robustness_reports.append(entry)
        session = self._require_session()
        await session.execute(
            text("""
                INSERT INTO walkforward_robustness_reports (
                    id, walkforward_id, user_id, payload
                ) VALUES (
                    :id, :walkforward_id, :user_id, CAST(:payload AS jsonb)
                )
                ON CONFLICT (walkforward_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    payload = EXCLUDED.payload,
                    recorded_at = timezone('utc', now())
                """),
            {
                "id": str(uuid4()),
                "walkforward_id": str(run_id),
                "user_id": str(user_id),
                "payload": as_json(payload),
            },
        )


class PostgresWalkForwardUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresWalkForwardUnitOfWork:
        return PostgresWalkForwardUnitOfWork(self._database)
