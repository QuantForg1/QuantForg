"""Backtest use cases — offline simulation only. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.backtest import (
    BacktestListDTO,
    BacktestRunDTO,
    GetBacktestCommand,
    ListBacktestsCommand,
    RunBacktestCommand,
)
from app.application.services.backtest_engine import (
    BacktestBarInput,
    BacktestEngine,
    BacktestRunInput,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.backtest import BacktestAssumptions
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.backtest import BacktestStatus, ReplayMode
from app.domain.exceptions.base import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class RunBacktestUseCase:
    backtest_uow_factory: Any
    engine: BacktestEngine
    audit: RecordAuditEventUseCase

    async def execute(self, command: RunBacktestCommand) -> BacktestRunDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required",
                details={"field": "request_id"},
            )
        if not command.bars and not command.ticks:
            raise ValidationError(
                "bars or ticks are required",
                details={"field": "bars"},
            )
        try:
            mode = ReplayMode(command.replay_mode.strip().lower())
            initial = Decimal(command.initial_balance)
            assumptions = BacktestAssumptions(
                spread=Decimal(command.spread),
                slippage=Decimal(command.slippage),
                fee_per_lot=Decimal(command.fee_per_lot),
                lot_size=Decimal(command.lot_size),
                stop_loss_distance=Decimal(command.stop_loss_distance),
                take_profit_distance=Decimal(command.take_profit_distance),
            )
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(
                "Invalid backtest input",
                details={"error": str(exc)},
            ) from exc

        bars = tuple(
            BacktestBarInput(
                open_time=b.open_time,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                close_time=b.close_time,
            )
            for b in command.bars
        )
        result = self.engine.run(
            BacktestRunInput(
                user_id=command.user_id,
                request_id=request_id,
                symbol=command.symbol,
                timeframe=command.timeframe,
                initial_balance=initial,
                bars=bars,
                ticks=command.ticks,
                replay_mode=mode,
                assumptions=assumptions,
                auto_analysis=command.auto_analysis,
                max_open_trades=max(1, command.max_open_trades),
                consult_execution_safety=command.consult_execution_safety,
            )
        )
        _ = self.engine.drain_events()

        async with self.backtest_uow_factory() as uow:
            await uow.runs.add(result.run)
            for trade in result.trades:
                await uow.trades.add(trade)
            await uow.commit()

        outcome = (
            AuditOutcome.SUCCESS
            if result.run.status is BacktestStatus.COMPLETED
            else AuditOutcome.FAILURE
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="backtest_run",
                resource_id=result.run.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "status": result.run.status.value,
                    "request_id": request_id,
                    "symbol": result.run.symbol,
                    "trade_count": result.run.trade_count,
                },
            )
        )
        return BacktestRunDTO.from_entities(result.run, list(result.trades))


@dataclass(frozen=True, slots=True)
class ListBacktestsUseCase:
    backtest_uow_factory: Any

    async def execute(self, command: ListBacktestsCommand) -> BacktestListDTO:
        limit = max(1, min(command.limit, 200))
        async with self.backtest_uow_factory() as uow:
            rows = await uow.runs.list_for_user(command.user_id, limit=limit)
        items = [BacktestRunDTO.from_entities(r) for r in rows]
        return BacktestListDTO(items=items, count=len(items))


@dataclass(frozen=True, slots=True)
class GetBacktestUseCase:
    backtest_uow_factory: Any

    async def execute(self, command: GetBacktestCommand) -> BacktestRunDTO:
        async with self.backtest_uow_factory() as uow:
            run = await uow.runs.get_for_user(command.user_id, command.backtest_id)
            if run is None:
                raise NotFoundError(
                    "Backtest not found",
                    details={"backtest_id": str(command.backtest_id)},
                )
            trades = await uow.trades.list_for_backtest(run.id)
        return BacktestRunDTO.from_entities(run, trades)
