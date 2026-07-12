"""Walk-Forward use cases — offline validation only. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.walkforward import (
    GetWalkForwardCommand,
    ListWalkForwardCommand,
    RunWalkForwardCommand,
    WalkForwardListDTO,
    WalkForwardRunDTO,
)
from app.application.services.backtest_engine import BacktestBarInput
from app.application.services.walkforward_engine import (
    WalkForwardEngine,
    WalkForwardRunInput,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.walkforward import WalkForwardWindowConfig
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.walkforward import (
    PromotionDecision,
    WalkForwardStatus,
)
from app.domain.exceptions.base import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class RunWalkForwardUseCase:
    walkforward_uow_factory: Any
    engine: WalkForwardEngine
    audit: RecordAuditEventUseCase

    async def execute(self, command: RunWalkForwardCommand) -> WalkForwardRunDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required",
                details={"field": "request_id"},
            )
        if not command.bars:
            raise ValidationError(
                "bars are required",
                details={"field": "bars"},
            )
        try:
            initial = Decimal(command.initial_balance)
            config = WalkForwardWindowConfig(
                in_sample_bars=command.in_sample_bars,
                out_of_sample_bars=command.out_of_sample_bars,
                step_bars=command.step_bars,
                anchored=command.anchored,
            )
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(
                "Invalid walk-forward input",
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
            WalkForwardRunInput(
                user_id=command.user_id,
                request_id=request_id,
                symbol=command.symbol,
                timeframe=command.timeframe,
                initial_balance=initial,
                bars=bars,
                window_config=config,
                optimize_params=command.optimize_params,
                auto_analysis=command.auto_analysis,
            )
        )
        _ = self.engine.drain_events()

        async with self.walkforward_uow_factory() as uow:
            await uow.runs.add(result.run)
            await uow.add_oos_metrics(
                user_id=command.user_id,
                run_id=result.run.id,
                payload=dict(result.run.aggregated_oos),
            )
            await uow.add_robustness_report(
                user_id=command.user_id,
                run_id=result.run.id,
                payload=dict(result.run.robustness),
            )
            await uow.commit()

        outcome = (
            AuditOutcome.SUCCESS
            if result.run.status is WalkForwardStatus.COMPLETED
            and result.run.promotion is PromotionDecision.PROMOTE_TO_PAPER
            else (
                AuditOutcome.DENIED
                if result.run.promotion is PromotionDecision.REJECT
                else AuditOutcome.FAILURE
            )
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="walkforward_run",
                resource_id=result.run.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "status": result.run.status.value,
                    "promotion": (
                        result.run.promotion.value if result.run.promotion else None
                    ),
                    "fold_count": result.run.fold_count,
                    "symbol": result.run.symbol,
                },
            )
        )
        return WalkForwardRunDTO.from_entity(result.run)


@dataclass(frozen=True, slots=True)
class ListWalkForwardUseCase:
    walkforward_uow_factory: Any

    async def execute(self, command: ListWalkForwardCommand) -> WalkForwardListDTO:
        limit = max(1, min(command.limit, 200))
        async with self.walkforward_uow_factory() as uow:
            rows = await uow.runs.list_for_user(command.user_id, limit=limit)
        items = [WalkForwardRunDTO.from_entity(r) for r in rows]
        return WalkForwardListDTO(items=items, count=len(items))


@dataclass(frozen=True, slots=True)
class GetWalkForwardUseCase:
    walkforward_uow_factory: Any

    async def execute(self, command: GetWalkForwardCommand) -> WalkForwardRunDTO:
        async with self.walkforward_uow_factory() as uow:
            run = await uow.runs.get_for_user(command.user_id, command.run_id)
            if run is None:
                raise NotFoundError(
                    "Walk-forward run not found",
                    details={"run_id": str(command.run_id)},
                )
        return WalkForwardRunDTO.from_entity(run)
