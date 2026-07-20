"""Execution gateway use cases — submit / cancel via Institutional Engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.execution import (
    ExecutionCancelCommand,
    ExecutionCancelDTO,
    ExecutionManageCommand,
    ExecutionPipelineDTO,
    ExecutionSubmitCommand,
    ExecutionSubmitDTO,
)
from app.application.services.execution_audit import ExecutionAuditService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.mt5_session_guard import (
    live_connection_meta,
    require_live_mt5_connection,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_gateway import ExecutionAttempt, ExecutionResult
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.execution import ExecutionAuditStage, ExecutionOutcome
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ValidationError
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SubmitExecutionUseCase:
    """Single submit path — Institutional Execution Engine → gateway."""

    mt5_uow_factory: Any
    execution_uow_factory: Any
    engine: InstitutionalExecutionEngine
    audit: RecordAuditEventUseCase
    execution_audit: ExecutionAuditService | None = None

    async def execute(self, command: ExecutionSubmitCommand) -> ExecutionSubmitDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required for idempotency",
                details={"field": "request_id"},
            )

        await require_live_mt5_connection(
            self.mt5_uow_factory,
            self.engine.gateway.adapter,
            command.user_id,
        )
        intent = parse_order_intent(
            symbol=command.symbol,
            side=command.side,
            order_type=command.order_type,
            volume=command.volume,
            price=command.price,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
            slippage=command.slippage,
            magic=command.magic,
            comment=command.comment,
            position=command.position,
            order_ticket=command.order_ticket,
            oms_kind=command.oms_kind,
        )

        async with self.execution_uow_factory() as uow:
            existing = await uow.attempts.get_by_request_id(command.user_id, request_id)

        if existing is not None:
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
            if self.execution_audit is not None:
                try:
                    await self.execution_audit.record(
                        user_id=command.user_id,
                        request_id=request_id,
                        stage=ExecutionAuditStage.REPLAY,
                        symbol=existing.symbol,
                        side=existing.side,
                        volume=str(existing.volume),
                        outcome=existing.outcome.value,
                        retcode=existing.retcode,
                        order_ticket=existing.order_ticket,
                        deal_ticket=existing.deal_ticket,
                        payload_out=existing.result_snapshot,
                        related_ids={"attempt_id": str(existing.id)},
                    )
                except Exception as exc:
                    logger.warning(
                        "execution_audit_failed",
                        stage="replay",
                        error=str(exc),
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

        connected, login = await live_connection_meta(
            self.mt5_uow_factory,
            self.engine.gateway.adapter,
            command.user_id,
        )
        async with self.execution_uow_factory() as uow:
            existing_decision = await uow.decisions.get_by_request_id(
                command.user_id, request_id
            )
            recent = await uow.decisions.list_recent_for_user(command.user_id)

        pipeline, decision = self.engine.run_submit(
            user_id=command.user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent_decisions=recent,
            existing_decision=existing_decision,
            action="submit",
        )

        if decision is not None and not decision.idempotent_replay:
            async with self.execution_uow_factory() as uow:
                await uow.decisions.add(decision)
                await uow.commit()

        if pipeline.outcome in {"rejected", "retry"}:
            raise ValidationError(
                pipeline.message or "Execution pipeline rejected order",
                details={
                    "code": "execution_pipeline_rejected",
                    "request_id": request_id,
                    "outcome": pipeline.outcome,
                    "rejection_reasons": list(pipeline.rejection_reasons),
                    "stages": [s.to_dict() for s in pipeline.stages],
                },
            )

        exec_result = pipeline.execution_result
        if exec_result is None:
            raise ValidationError(
                "Execution pipeline produced no broker result",
                details={"request_id": request_id, "outcome": pipeline.outcome},
            )

        attempt = ExecutionAttempt.record(
            user_id=command.user_id,
            request_id=request_id,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            volume=intent.volume.value,
            result=exec_result,
            request_snapshot={
                **intent.to_dict(),
                "pipeline_latency_ms": pipeline.latency_ms,
                "stages": [s.to_dict() for s in pipeline.stages],
            },
        )
        async with self.execution_uow_factory() as uow:
            await uow.attempts.add(attempt)
            await uow.commit()

        if self.execution_audit is not None:
            try:
                stage_latencies = {
                    s.stage: round(s.elapsed_ms, 3) for s in pipeline.stages
                }
                gateway_ms = None
                for key, val in stage_latencies.items():
                    lowered = key.strip().lower()
                    if "broker" in lowered or lowered in {"submit", "submission"}:
                        gateway_ms = val
                        break
                await self.execution_audit.record(
                    user_id=command.user_id,
                    request_id=request_id,
                    stage=ExecutionAuditStage.SUBMIT,
                    symbol=intent.symbol,
                    side=intent.side.value,
                    volume=str(intent.volume.value),
                    outcome=exec_result.outcome.value,
                    retcode=exec_result.retcode,
                    order_ticket=exec_result.order_ticket,
                    deal_ticket=exec_result.deal_ticket,
                    latency_ms=pipeline.latency_ms,
                    gateway_latency_ms=(
                        float(gateway_ms) if gateway_ms is not None else None
                    ),
                    railway_processing_ms=None,
                    cloudflare_latency_ms=None,
                    slippage=str(command.slippage),
                    payload_in=dict(attempt.request_snapshot),
                    payload_out=exec_result.to_dict(),
                    related_ids={"attempt_id": str(attempt.id)},
                )
            except Exception as exc:
                logger.warning(
                    "execution_audit_failed",
                    stage="submit",
                    error=str(exc),
                )

        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=(
                    AuditOutcome.SUCCESS
                    if exec_result.outcome is ExecutionOutcome.SUCCESS
                    else (
                        AuditOutcome.DENIED
                        if exec_result.outcome is ExecutionOutcome.DISABLED
                        else AuditOutcome.FAILURE
                    )
                ),
                resource_type="execution_attempt",
                resource_id=attempt.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "outcome": exec_result.outcome.value,
                    "retcode": exec_result.retcode,
                    "request_id": request_id,
                    "symbol": intent.symbol,
                    "latency_ms": pipeline.latency_ms,
                },
            )
        )

        if exec_result.outcome is ExecutionOutcome.DISABLED:
            raise AuthorizationError(
                exec_result.message,
                code="execution_disabled",
                details={
                    "request_id": request_id,
                    "outcome": exec_result.outcome.value,
                    "retcode": exec_result.retcode,
                    "stages": [s.to_dict() for s in pipeline.stages],
                },
            )

        dto = ExecutionSubmitDTO.from_entity(attempt)
        return ExecutionSubmitDTO(
            id=dto.id,
            request_id=dto.request_id,
            outcome=dto.outcome,
            retcode=dto.retcode,
            message=dto.message,
            symbol=dto.symbol,
            side=dto.side,
            order_type=dto.order_type,
            volume=dto.volume,
            order_ticket=dto.order_ticket,
            deal_ticket=dto.deal_ticket,
            price=dto.price,
            retryable=dto.retryable,
            idempotent_replay=dto.idempotent_replay,
            submitted_at=dto.submitted_at,
            stages=[s.to_dict() for s in pipeline.stages],
            latency_ms=pipeline.latency_ms,
            journal_entry=pipeline.journal_entry,
        )


@dataclass(frozen=True, slots=True)
class CancelExecutionUseCase:
    mt5_uow_factory: Any
    execution_uow_factory: Any
    engine: InstitutionalExecutionEngine
    audit: RecordAuditEventUseCase

    async def execute(self, command: ExecutionCancelCommand) -> ExecutionCancelDTO:
        request_id = (
            command.request_id.strip() or f"cancel_{command.ticket}_{uuid4().hex[:8]}"
        )
        await require_live_mt5_connection(
            self.mt5_uow_factory,
            self.engine.gateway.adapter,
            command.user_id,
        )
        connected, _login = await live_connection_meta(
            self.mt5_uow_factory,
            self.engine.gateway.adapter,
            command.user_id,
        )
        pipeline = self.engine.run_cancel(
            user_id=command.user_id,
            request_id=request_id,
            ticket=command.ticket,
            symbol=command.symbol,
            connected=connected,
        )
        exec_result = pipeline.execution_result
        if exec_result is not None:
            attempt = ExecutionAttempt.record(
                user_id=command.user_id,
                request_id=request_id,
                symbol=command.symbol or f"ticket:{command.ticket}",
                side="cancel",
                order_type="pending",
                volume=Decimal("0"),
                result=exec_result,
                request_snapshot={
                    "ticket": command.ticket,
                    "action": "cancel",
                    "stages": [s.to_dict() for s in pipeline.stages],
                },
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
                        if exec_result.outcome is ExecutionOutcome.SUCCESS
                        else (
                            AuditOutcome.DENIED
                            if exec_result.outcome is ExecutionOutcome.DISABLED
                            else AuditOutcome.FAILURE
                        )
                    ),
                    resource_type="execution_cancel",
                    resource_id=attempt.id,
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                    metadata={
                        "ticket": command.ticket,
                        "outcome": exec_result.outcome.value,
                        "request_id": request_id,
                    },
                )
            )

            if exec_result.outcome is ExecutionOutcome.DISABLED:
                raise AuthorizationError(
                    exec_result.message,
                    code="execution_disabled",
                    details={"request_id": request_id, "ticket": command.ticket},
                )

        return ExecutionCancelDTO(
            request_id=request_id,
            outcome=pipeline.outcome,
            message=pipeline.message,
            ticket=command.ticket,
            stages=[s.to_dict() for s in pipeline.stages],
            latency_ms=pipeline.latency_ms,
            journal_entry=pipeline.journal_entry,
            rejection_reasons=list(pipeline.rejection_reasons),
        )


@dataclass(frozen=True, slots=True)
class ManageExecutionUseCase:
    """OMS actions routed through the same institutional pipeline."""

    mt5_uow_factory: Any
    execution_uow_factory: Any
    engine: InstitutionalExecutionEngine
    audit: RecordAuditEventUseCase
    submit: SubmitExecutionUseCase
    cancel: CancelExecutionUseCase

    async def execute(self, command: ExecutionManageCommand) -> ExecutionPipelineDTO:
        action = command.action.strip().lower()
        request_id = command.request_id.strip() or f"{action}_{uuid4().hex[:10]}"

        if action == "cancel_pending":
            cancel_dto = await self.cancel.execute(
                ExecutionCancelCommand(
                    user_id=command.user_id,
                    request_id=request_id,
                    ticket=int(command.ticket or 0),
                    symbol=command.symbol,
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
            )
            return ExecutionPipelineDTO(
                request_id=cancel_dto.request_id,
                action=action,
                outcome=cancel_dto.outcome,
                message=cancel_dto.message,
                stages=cancel_dto.stages,
                rejection_reasons=cancel_dto.rejection_reasons,
                latency_ms=cancel_dto.latency_ms,
                journal_entry=cancel_dto.journal_entry,
            )

        # Build OMS intent → same submit pipeline (one broker entry point)
        side = command.side
        order_type = command.order_type or "market"
        volume = command.volume or "0.01"
        comment = command.comment or ""
        position = int(command.ticket or 0)
        order_ticket = 0
        oms_kind = ""

        if action in {"close", "partial_close", "close_all"}:
            if not side:
                raise ValidationError(
                    "side is required for close (opposite of position)",
                    details={"field": "side", "component": "oms.close"},
                )
            order_type = "market"
            oms_kind = "close" if action != "partial_close" else "partial_close"
            if command.ticket:
                comment = f"close:{command.ticket}" + (f"|{comment}" if comment else "")
        elif action == "reverse":
            if not side:
                raise ValidationError(
                    "side is required for reverse (close side first)",
                    details={"field": "side", "component": "oms.reverse"},
                )
            order_type = "market"
            oms_kind = "reverse"
            if command.ticket:
                comment = f"reverse:{command.ticket}"
        elif action == "modify":
            # Pending order modify (price / SL / TP)
            oms_kind = "modify_pending"
            order_ticket = int(command.ticket or 0)
            position = 0
            if command.ticket:
                comment = f"modify:{command.ticket}"
        elif action in {"modify_sltp", "move_sl", "move_tp"}:
            oms_kind = "sltp"
            order_type = "market"
            if command.ticket:
                comment = f"modify-sltp:{command.ticket}"
        elif action == "trailing_stop":
            trail = command.trailing_points or ""
            comment = f"trail:{trail}"
            oms_kind = "sltp"
            if command.ticket:
                comment = f"modify-sltp:{command.ticket}|{comment}"
        elif action == "break_even":
            comment = "be:1"
            oms_kind = "sltp"
            if command.ticket:
                comment = f"modify-sltp:{command.ticket}|be:1"
        else:
            raise ValidationError(
                f"Unsupported OMS action '{action}'",
                details={
                    "component": "oms",
                    "allowed": [
                        "close",
                        "partial_close",
                        "close_all",
                        "reverse",
                        "modify",
                        "modify_sltp",
                        "move_sl",
                        "move_tp",
                        "trailing_stop",
                        "break_even",
                        "cancel_pending",
                    ],
                },
            )

        submit_dto = await self.submit.execute(
            ExecutionSubmitCommand(
                user_id=command.user_id,
                request_id=request_id,
                symbol=command.symbol,
                side=side or "buy",
                order_type=order_type,
                volume=volume,
                price=command.price,
                stop_loss=command.stop_loss,
                take_profit=command.take_profit,
                slippage=command.slippage,
                magic=command.magic,
                comment=comment[:64],
                position=position,
                order_ticket=order_ticket,
                oms_kind=oms_kind,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return ExecutionPipelineDTO(
            request_id=submit_dto.request_id,
            action=action,
            outcome=submit_dto.outcome,
            message=submit_dto.message,
            stages=list(submit_dto.stages or []),
            latency_ms=submit_dto.latency_ms or 0.0,
            journal_entry=submit_dto.journal_entry,
            order_ticket=submit_dto.order_ticket,
            deal_ticket=submit_dto.deal_ticket,
            price=submit_dto.price,
        )


# End of OMS use cases
