"""Postgres persistence for Backtesting Engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.backtest import BacktestRun, SimulatedTrade
from app.domain.enums.backtest import (
    BacktestStatus,
    ReplayMode,
    SimulatedExitReason,
    SimulatedTradeSide,
    SimulatedTradeStatus,
)
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    json_list,
    parse_datetime,
    parse_datetime_optional,
    parse_decimal,
    parse_decimal_optional,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _run_from_row(row: Any) -> BacktestRun:
    return BacktestRun(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"] or "m15"),
        status=BacktestStatus(str(row["status"])),
        replay_mode=ReplayMode(str(row["replay_mode"] or "candle")),
        initial_balance=parse_decimal(row["initial_balance"]),
        assumptions=json_dict(row["assumptions"]),
        metrics=json_dict(row["metrics"]),
        equity_curve=[
            dict(p) if isinstance(p, dict) else {}
            for p in json_list(row["equity_curve"])
        ],
        portfolio_snapshot=json_dict(row["portfolio_snapshot"]),
        trade_count=int(row["trade_count"] or 0),
        bar_count=int(row["bar_count"] or 0),
        replay_state=json_dict(row["replay_state"]),
        error_message=str(row["error_message"] or ""),
        started_at=parse_datetime_optional(row["started_at"]),
        finished_at=parse_datetime_optional(row["finished_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _trade_from_row(row: Any) -> SimulatedTrade:
    created = parse_datetime(row["created_at"])
    exit_reason = row["exit_reason"]
    bar_close = row["bar_index_close"]
    return SimulatedTrade(
        id=parse_uuid(row["id"]),
        backtest_id=parse_uuid(row["backtest_id"]),
        symbol=str(row["symbol"]),
        side=SimulatedTradeSide(str(row["side"])),
        status=SimulatedTradeStatus(str(row["status"])),
        volume=parse_decimal(row["volume"]),
        entry_price=parse_decimal(row["entry_price"]),
        exit_price=parse_decimal_optional(row["exit_price"]),
        stop_loss=parse_decimal_optional(row["stop_loss"]),
        take_profit=parse_decimal_optional(row["take_profit"]),
        spread=parse_decimal(row["spread"], "0"),
        slippage=parse_decimal(row["slippage"], "0"),
        fees=parse_decimal(row["fees"], "0"),
        pnl=parse_decimal(row["pnl"], "0"),
        exit_reason=(SimulatedExitReason(str(exit_reason)) if exit_reason else None),
        opened_at=parse_datetime(row["opened_at"]),
        closed_at=parse_datetime_optional(row["closed_at"]),
        bar_index_open=int(row["bar_index_open"] or 0),
        bar_index_close=int(bar_close) if bar_close is not None else None,
        created_at=created,
        updated_at=created,
    )


class PostgresBacktestRunRepository:
    def __init__(self, uow: PostgresBacktestUnitOfWork) -> None:
        self._uow = uow

    async def add(self, run: BacktestRun) -> BacktestRun:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO backtest_runs (
                    id, user_id, request_id, symbol, timeframe, status, replay_mode,
                    initial_balance, assumptions, metrics, equity_curve,
                    portfolio_snapshot, replay_state, trade_count, bar_count,
                    error_message, started_at, finished_at, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :request_id, :symbol, :timeframe, :status,
                    :replay_mode, :initial_balance, CAST(:assumptions AS jsonb),
                    CAST(:metrics AS jsonb), CAST(:equity_curve AS jsonb),
                    CAST(:portfolio_snapshot AS jsonb), CAST(:replay_state AS jsonb),
                    :trade_count, :bar_count, :error_message, :started_at,
                    :finished_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    request_id = EXCLUDED.request_id,
                    symbol = EXCLUDED.symbol,
                    timeframe = EXCLUDED.timeframe,
                    status = EXCLUDED.status,
                    replay_mode = EXCLUDED.replay_mode,
                    initial_balance = EXCLUDED.initial_balance,
                    assumptions = EXCLUDED.assumptions,
                    metrics = EXCLUDED.metrics,
                    equity_curve = EXCLUDED.equity_curve,
                    portfolio_snapshot = EXCLUDED.portfolio_snapshot,
                    replay_state = EXCLUDED.replay_state,
                    trade_count = EXCLUDED.trade_count,
                    bar_count = EXCLUDED.bar_count,
                    error_message = EXCLUDED.error_message,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(run.id),
                "user_id": str(run.user_id),
                "request_id": run.request_id,
                "symbol": run.symbol,
                "timeframe": run.timeframe,
                "status": run.status.value,
                "replay_mode": run.replay_mode.value,
                "initial_balance": str(run.initial_balance),
                "assumptions": as_json(run.assumptions),
                "metrics": as_json(run.metrics),
                "equity_curve": as_json(run.equity_curve),
                "portfolio_snapshot": as_json(run.portfolio_snapshot),
                "replay_state": as_json(run.replay_state),
                "trade_count": run.trade_count,
                "bar_count": run.bar_count,
                "error_message": run.error_message,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
            },
        )
        return run

    async def get(self, backtest_id: UUID) -> BacktestRun | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM backtest_runs WHERE id = :id"),
            {"id": str(backtest_id)},
        )
        row = result.mappings().first()
        return _run_from_row(row) if row else None

    async def get_for_user(
        self, user_id: UUID, backtest_id: UUID
    ) -> BacktestRun | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM backtest_runs
                WHERE id = :id AND user_id = :user_id
                """
            ),
            {"id": str(backtest_id), "user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _run_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[BacktestRun]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM backtest_runs
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_run_from_row(r) for r in result.mappings().all()]


class PostgresSimulatedTradeRepository:
    def __init__(self, uow: PostgresBacktestUnitOfWork) -> None:
        self._uow = uow

    async def add(self, trade: SimulatedTrade) -> SimulatedTrade:
        session = self._uow._require_session()
        owner = await session.execute(
            text("SELECT user_id FROM backtest_runs WHERE id = :id"),
            {"id": str(trade.backtest_id)},
        )
        owner_row = owner.mappings().first()
        if owner_row is None:
            msg = f"backtest_run {trade.backtest_id} not found for trade insert"
            raise RuntimeError(msg)
        user_id = str(owner_row["user_id"])
        await session.execute(
            text(
                """
                INSERT INTO backtest_trades (
                    id, backtest_id, user_id, symbol, side, status, volume,
                    entry_price, exit_price, stop_loss, take_profit, spread,
                    slippage, fees, pnl, exit_reason, opened_at, closed_at,
                    bar_index_open, bar_index_close, created_at
                ) VALUES (
                    :id, :backtest_id, :user_id, :symbol, :side, :status, :volume,
                    :entry_price, :exit_price, :stop_loss, :take_profit, :spread,
                    :slippage, :fees, :pnl, :exit_reason, :opened_at, :closed_at,
                    :bar_index_open, :bar_index_close, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    backtest_id = EXCLUDED.backtest_id,
                    user_id = EXCLUDED.user_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    status = EXCLUDED.status,
                    volume = EXCLUDED.volume,
                    entry_price = EXCLUDED.entry_price,
                    exit_price = EXCLUDED.exit_price,
                    stop_loss = EXCLUDED.stop_loss,
                    take_profit = EXCLUDED.take_profit,
                    spread = EXCLUDED.spread,
                    slippage = EXCLUDED.slippage,
                    fees = EXCLUDED.fees,
                    pnl = EXCLUDED.pnl,
                    exit_reason = EXCLUDED.exit_reason,
                    opened_at = EXCLUDED.opened_at,
                    closed_at = EXCLUDED.closed_at,
                    bar_index_open = EXCLUDED.bar_index_open,
                    bar_index_close = EXCLUDED.bar_index_close
                """
            ),
            {
                "id": str(trade.id),
                "backtest_id": str(trade.backtest_id),
                "user_id": user_id,
                "symbol": trade.symbol,
                "side": trade.side.value,
                "status": trade.status.value,
                "volume": str(trade.volume),
                "entry_price": str(trade.entry_price),
                "exit_price": (
                    str(trade.exit_price) if trade.exit_price is not None else None
                ),
                "stop_loss": (
                    str(trade.stop_loss) if trade.stop_loss is not None else None
                ),
                "take_profit": (
                    str(trade.take_profit) if trade.take_profit is not None else None
                ),
                "spread": str(trade.spread),
                "slippage": str(trade.slippage),
                "fees": str(trade.fees),
                "pnl": str(trade.pnl),
                "exit_reason": (trade.exit_reason.value if trade.exit_reason else None),
                "opened_at": trade.opened_at,
                "closed_at": trade.closed_at,
                "bar_index_open": trade.bar_index_open,
                "bar_index_close": trade.bar_index_close,
                "created_at": trade.created_at,
            },
        )
        return trade

    async def list_for_backtest(
        self, backtest_id: UUID, *, limit: int = 500
    ) -> list[SimulatedTrade]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM backtest_trades
                WHERE backtest_id = :backtest_id
                ORDER BY opened_at ASC
                LIMIT :limit
                """
            ),
            {"backtest_id": str(backtest_id), "limit": limit},
        )
        return [_trade_from_row(r) for r in result.mappings().all()]


class PostgresBacktestUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.runs = PostgresBacktestRunRepository(self)
        self.trades = PostgresSimulatedTradeRepository(self)


class PostgresBacktestUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresBacktestUnitOfWork:
        return PostgresBacktestUnitOfWork(self._database)
