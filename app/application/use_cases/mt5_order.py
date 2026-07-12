"""MT5 order validation use cases — check/calc only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.mt5 import (
    MT5OrderCalculateDTO,
    MT5OrderValidateCommand,
    MT5OrderValidationDTO,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5_order import OrderIntent, TradeValidation
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.interfaces.mt5_order import RETCODE_DONE
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)


def _parse_intent(command: MT5OrderValidateCommand) -> OrderIntent:
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
            "Invalid order intent",
            details={"error": str(exc)},
        ) from exc


async def _require_active_connection(uow_factory: Any, user_id: UUID) -> None:
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)
    if connection is None or not connection.connected:
        raise NotFoundError("No active MT5 connection")


@dataclass(frozen=True, slots=True)
class ValidateMT5OrderUseCase:
    uow_factory: Any
    validation_service: MT5OrderValidationService
    audit: RecordAuditEventUseCase

    async def execute(self, command: MT5OrderValidateCommand) -> MT5OrderValidationDTO:
        await _require_active_connection(self.uow_factory, command.user_id)
        intent = _parse_intent(command)
        try:
            result = self.validation_service.validate_order(intent)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "MT5 order validation failed",
                details={"error": str(exc)},
            ) from exc

        # Re-bind user_id on a persisted copy
        stored = TradeValidation.record(
            user_id=command.user_id,
            symbol=result.symbol,
            side=result.side,
            order_type=result.order_type,
            volume=result.volume,
            valid=result.valid,
            retcode=result.retcode,
            expected_margin=result.expected_margin,
            estimated_profit=result.estimated_profit,
            messages=list(result.messages),
            checks=dict(result.checks),
            request_snapshot=dict(result.request_snapshot),
        )
        async with self.uow_factory() as uow:
            await uow.validations.add(stored)
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.READ,
                outcome=(
                    AuditOutcome.SUCCESS if stored.valid else AuditOutcome.FAILURE
                ),
                resource_type="mt5_order_validation",
                resource_id=stored.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="MT5 order validation",
                metadata={
                    "valid": stored.valid,
                    "retcode": stored.retcode,
                    "symbol": stored.symbol,
                },
            )
        )
        return MT5OrderValidationDTO.from_entity(stored)


@dataclass(frozen=True, slots=True)
class CalculateMT5OrderUseCase:
    uow_factory: Any
    validation_service: MT5OrderValidationService

    async def execute(self, command: MT5OrderValidateCommand) -> MT5OrderCalculateDTO:
        await _require_active_connection(self.uow_factory, command.user_id)
        intent = _parse_intent(command)
        try:
            request, margin, profit = self.validation_service.calculate(intent)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "MT5 order calculation failed",
                details={"error": str(exc)},
            ) from exc
        messages = [
            f"margin: {margin.comment} ({margin.retcode})",
            f"profit: {profit.comment} ({profit.retcode})",
        ]
        return MT5OrderCalculateDTO(
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            volume=str(intent.volume.value),
            price=str(request.price),
            expected_margin=str(margin.margin),
            estimated_profit=str(profit.profit),
            retcode=(
                margin.retcode if margin.retcode != RETCODE_DONE else profit.retcode
            ),
            messages=tuple(messages),
            request_snapshot=request.to_dict(),
        )
