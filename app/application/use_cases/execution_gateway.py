"""Execution gateway use case — submit gated by EXECUTION_ENABLED."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.execution import ExecutionSubmitCommand, ExecutionSubmitDTO
from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.mt5_session_guard import require_live_mt5_connection
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_gateway import ExecutionAttempt, ExecutionResult
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.execution import ExecutionOutcome
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)


def _parse_intent(command: ExecutionSubmitCommand) -> OrderIntent:
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
            "Invalid execution submit intent",
            details={"error": str(exc)},
        ) from exc


@dataclass(frozen=True, slots=True)
class SubmitExecutionUseCase:
    mt5_uow_factory: Any
    execution_uow_factory: Any
    gateway: ExecutionGateway
    audit: RecordAuditEventUseCase

    async def execute(self, command: ExecutionSubmitCommand) -> ExecutionSubmitDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required for idempotency",
                details={"field": "request_id"},
            )

        await require_live_mt5_connection(
            self.mt5_uow_factory, self.gateway.adapter, command.user_id
        )
        intent = _parse_intent(command)

        async with self.execution_uow_factory() as uow:
            existing = await uow.attempts.get_by_request_id(command.user_id, request_id)

        if existing is not None:
            # Idempotent replay — never re-send
            replay = ExecutionAttempt.record(
                user_id=existing.user_id,
                request_id=existing.request_id,
                symbol=existing.symbol,
                side=existing.side,
                order_type=existing.order_type,
                volume=existing.volume,
                result=ExecutionResult(
                    outcome=existing.outcome,
                    retcode=existing.retcode,
                    message=existing.message,
                    order_ticket=existing.order_ticket,
                    deal_ticket=existing.deal_ticket,
                    volume=existing.volume,
                    price=existing.price,
                    symbol=existing.symbol,
                    request_id=existing.request_id,
                    retryable=existing.retryable,
                ),
                request_snapshot=dict(existing.request_snapshot),
                idempotent_replay=True,
                entity_id=existing.id,
            )
            if existing.outcome is ExecutionOutcome.DISABLED:
                raise AuthorizationError(
                    existing.message,
                    code="execution_disabled",
                    details={
                        "request_id": request_id,
                        "outcome": existing.outcome.value,
                        "retcode": existing.retcode,
                        "idempotent_replay": True,
                    },
                )
            return ExecutionSubmitDTO.from_entity(replay)

        result = self.gateway.submit(
            intent, user_id=command.user_id, request_id=request_id
        )
        _ = self.gateway.drain_events()

        attempt = ExecutionAttempt.record(
            user_id=command.user_id,
            request_id=request_id,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            volume=intent.volume.value,
            result=result,
            request_snapshot=intent.to_dict(),
        )
        async with self.execution_uow_factory() as uow:
            await uow.attempts.add(attempt)
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=(
                    AuditOutcome.SUCCESS
                    if result.outcome is ExecutionOutcome.SUCCESS
                    else (
                        AuditOutcome.DENIED
                        if result.outcome is ExecutionOutcome.DISABLED
                        else AuditOutcome.FAILURE
                    )
                ),
                resource_type="execution_attempt",
                resource_id=attempt.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "outcome": result.outcome.value,
                    "retcode": result.retcode,
                    "request_id": request_id,
                    "symbol": intent.symbol,
                },
            )
        )

        if result.outcome is ExecutionOutcome.DISABLED:
            raise AuthorizationError(
                result.message,
                code="execution_disabled",
                details={
                    "request_id": request_id,
                    "outcome": result.outcome.value,
                    "retcode": result.retcode,
                },
            )

        return ExecutionSubmitDTO.from_entity(attempt)
