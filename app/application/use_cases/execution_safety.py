"""Execution safety use case — check only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.execution import ExecutionCheckCommand, ExecutionCheckDTO
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.mt5_session_guard import live_connection_meta
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_safety import ExecutionDecisionRecord
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.execution_engine.reasons import humanize_reasons
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)


def _parse_intent(command: ExecutionCheckCommand) -> OrderIntent:
    try:
        side = OrderSide(command.side.strip().lower())
        order_type = OrderType(command.order_type.strip().lower())
        volume = LotSize.of(command.volume)
        price = (
            Decimal(command.price)
            if command.price is not None and command.price != ""
            else None
        )
        sl = StopLoss.of(command.stop_loss) if command.stop_loss else None
        tp = TakeProfit.of(command.take_profit) if command.take_profit else None
        return OrderIntent(
            symbol=command.symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            slippage=Slippage.of(command.slippage),
            magic=MagicNumber.of(command.magic),
            comment=command.comment,
        )
    except (ValidationError, ValueError) as exc:
        raise ValidationError(
            "Invalid execution check intent",
            details={"error": str(exc)},
        ) from exc


async def _active_connection_meta(
    uow_factory: Any, adapter: Any, user_id: UUID
) -> tuple[bool, int | None]:
    return await live_connection_meta(uow_factory, adapter, user_id)


@dataclass(frozen=True, slots=True)
class CheckExecutionSafetyUseCase:
    mt5_uow_factory: Any
    execution_uow_factory: Any
    safety_service: ExecutionSafetyService
    audit: RecordAuditEventUseCase

    async def execute(self, command: ExecutionCheckCommand) -> ExecutionCheckDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required for idempotency",
                details={"field": "request_id"},
            )

        intent = _parse_intent(command)
        connected, login = await _active_connection_meta(
            self.mt5_uow_factory, self.safety_service.adapter, command.user_id
        )
        if not connected:
            raise NotFoundError("No active MT5 connection")

        async with self.execution_uow_factory() as uow:
            existing = await uow.decisions.get_by_request_id(
                command.user_id, request_id
            )
            recent = await uow.decisions.list_recent_for_user(command.user_id)

        try:
            record = self.safety_service.decide(
                user_id=command.user_id,
                request_id=request_id,
                intent=intent,
                connected=connected,
                login=login,
                recent=recent,
                existing_by_request_id=existing,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "Execution safety check failed",
                details={"error": str(exc)},
            ) from exc

        # Human-readable rejection reasons for the desk
        if record.rejection_reasons:
            record = ExecutionDecisionRecord.record(
                user_id=record.user_id,
                request_id=record.request_id,
                decision=record.decision,
                symbol=record.symbol,
                side=record.side,
                order_type=record.order_type,
                volume=record.volume,
                rejection_reasons=humanize_reasons(record.rejection_reasons),
                warnings=list(record.warnings),
                calculated_risk=dict(record.calculated_risk),
                checks=dict(record.checks),
                request_fingerprint=record.request_fingerprint,
                request_snapshot=dict(record.request_snapshot),
                idempotent_replay=record.idempotent_replay,
                entity_id=record.id,
            )

        if not record.idempotent_replay:
            async with self.execution_uow_factory() as uow:
                await uow.decisions.add(record)
                await uow.commit()

        # Drain events (in-process buffer; no bus required this layer)
        _ = self.safety_service.drain_events()

        outcome = (
            AuditOutcome.SUCCESS
            if record.decision.value == "allow"
            else (
                AuditOutcome.DENIED
                if record.decision.value == "reject"
                else AuditOutcome.FAILURE
            )
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="execution_decision",
                resource_id=record.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "decision": record.decision.value,
                    "request_id": request_id,
                    "symbol": record.symbol,
                    "idempotent_replay": record.idempotent_replay,
                },
            )
        )
        return ExecutionCheckDTO.from_entity(record)
