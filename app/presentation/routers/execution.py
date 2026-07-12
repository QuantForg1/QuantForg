"""Execution safety + gateway API.

``/check`` — safety decisions only (never order_send).
``/submit`` — Execution Gateway (DISABLED by default → HTTP 403).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.application.dto.execution import (
    ExecutionCheckCommand,
    ExecutionSubmitCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.execution import (
    CheckExecutionDep,
    SubmitExecutionDep,
)
from app.presentation.schemas.execution import (
    ExecutionCheckRequest,
    ExecutionCheckResponse,
    ExecutionSubmitRequest,
    ExecutionSubmitResponse,
)

router = APIRouter(prefix="/execution", tags=["execution"])


@router.post("/check", response_model=ExecutionCheckResponse)
async def execution_check(
    body: ExecutionCheckRequest,
    request: Request,
    user: CurrentUser,
    check: CheckExecutionDep,
) -> ExecutionCheckResponse:
    """Run the execution safety pipeline. Returns ALLOW | REJECT | RETRY.

    Never places a live order. Never calls order_send().
    """
    ip, ua = get_client_meta(request)
    dto = await check.execute(
        ExecutionCheckCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            slippage=body.slippage,
            magic=body.magic,
            comment=body.comment,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return ExecutionCheckResponse(
        id=dto.id,
        request_id=dto.request_id,
        decision=dto.decision,
        symbol=dto.symbol,
        side=dto.side,
        order_type=dto.order_type,
        volume=dto.volume,
        rejection_reasons=list(dto.rejection_reasons),
        warnings=list(dto.warnings),
        calculated_risk=dict(dto.calculated_risk),
        checks=dict(dto.checks),
        idempotent_replay=dto.idempotent_replay,
        decided_at=dto.decided_at,
    )


@router.post("/submit", response_model=ExecutionSubmitResponse)
async def execution_submit(
    body: ExecutionSubmitRequest,
    request: Request,
    user: CurrentUser,
    submit: SubmitExecutionDep,
) -> ExecutionSubmitResponse:
    """Submit via Execution Gateway.

    When ``EXECUTION_ENABLED=false`` (default), responds with HTTP 403
    and never calls the broker ``order_send``.
    """
    ip, ua = get_client_meta(request)
    dto = await submit.execute(
        ExecutionSubmitCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            slippage=body.slippage,
            magic=body.magic,
            comment=body.comment,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return ExecutionSubmitResponse(
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
    )
