"""Execution safety + institutional gateway API.

``/check`` — safety decisions only (never order_send).
``/submit`` — Institutional Execution Engine → Gateway (DISABLED by default → HTTP 403).
``/cancel`` — pending cancel via same gateway gate.
``/manage`` — OMS actions through the same pipeline.
``/journal`` / ``/analytics`` — observable post-trade surfaces.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.application.dto.execution import (
    ExecutionCancelCommand,
    ExecutionCheckCommand,
    ExecutionManageCommand,
    ExecutionSubmitCommand,
)
from app.domain.execution_intelligence.analytics import compute_execution_analytics
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.execution import (
    CancelExecutionDep,
    CheckExecutionDep,
    JournalDep,
    ManageExecutionDep,
    SubmitExecutionDep,
    get_execution_uow_factory,
)
from app.presentation.schemas.execution import (
    ExecutionAnalyticsResponse,
    ExecutionCancelRequest,
    ExecutionCancelResponse,
    ExecutionCheckRequest,
    ExecutionCheckResponse,
    ExecutionJournalResponse,
    ExecutionManageRequest,
    ExecutionManageResponse,
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
    """Submit via Institutional Execution Engine → Execution Gateway.

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
            position=body.position,
            order_ticket=body.order_ticket,
            oms_kind=body.oms_kind,
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
        stages=list(dto.stages or []),
        latency_ms=dto.latency_ms,
        journal_entry=dto.journal_entry,
    )


@router.post("/cancel", response_model=ExecutionCancelResponse)
async def execution_cancel(
    body: ExecutionCancelRequest,
    request: Request,
    user: CurrentUser,
    cancel: CancelExecutionDep,
) -> ExecutionCancelResponse:
    """Cancel a pending order through the gated Execution Gateway."""
    ip, ua = get_client_meta(request)
    dto = await cancel.execute(
        ExecutionCancelCommand(
            user_id=user.id,
            request_id=body.request_id,
            ticket=body.ticket,
            symbol=body.symbol,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return ExecutionCancelResponse(
        request_id=dto.request_id,
        outcome=dto.outcome,
        message=dto.message,
        ticket=dto.ticket,
        stages=list(dto.stages),
        latency_ms=dto.latency_ms,
        journal_entry=dto.journal_entry,
        rejection_reasons=list(dto.rejection_reasons or []),
    )


@router.post("/manage", response_model=ExecutionManageResponse)
async def execution_manage(
    body: ExecutionManageRequest,
    request: Request,
    user: CurrentUser,
    manage: ManageExecutionDep,
) -> ExecutionManageResponse:
    """OMS actions (close / reverse / modify / trail / BE) via one pipeline."""
    ip, ua = get_client_meta(request)
    dto = await manage.execute(
        ExecutionManageCommand(
            user_id=user.id,
            request_id=body.request_id,
            action=body.action,
            symbol=body.symbol,
            ticket=body.ticket,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            slippage=body.slippage,
            magic=body.magic,
            comment=body.comment,
            trailing_points=body.trailing_points,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return ExecutionManageResponse(
        request_id=dto.request_id,
        action=dto.action,
        outcome=dto.outcome,
        message=dto.message,
        stages=list(dto.stages),
        latency_ms=dto.latency_ms,
        rejection_reasons=list(dto.rejection_reasons or []),
        journal_entry=dto.journal_entry,
        order_ticket=dto.order_ticket,
        deal_ticket=dto.deal_ticket,
        price=dto.price,
    )


@router.get("/journal", response_model=ExecutionJournalResponse)
async def execution_journal(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> ExecutionJournalResponse:
    items = journal.list_for_user(str(user.id), limit=limit)
    return ExecutionJournalResponse(items=items, count=len(items))


async def _load_attempts(user_id: UUID, limit: int = 200) -> list[dict[str, Any]]:
    try:
        factory = get_execution_uow_factory()
    except RuntimeError:
        return []
    try:
        async with factory() as uow:
            rows = await uow.attempts.list_for_user(user_id, limit=limit)
            return [a.to_dict() for a in rows]
    except Exception:
        return []


@router.get("/analytics", response_model=ExecutionAnalyticsResponse)
async def execution_analytics(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> ExecutionAnalyticsResponse:
    attempts = await _load_attempts(user.id, limit=limit)
    # Enrich with journal latency when attempt lacks latency_ms
    journal_rows = journal.list_for_user(str(user.id), limit=limit)
    by_req = {str(j.get("request_id")): j for j in journal_rows if j.get("request_id")}
    enriched: list[dict[str, Any]] = []
    for a in attempts:
        row = dict(a)
        j = by_req.get(str(a.get("request_id")))
        if j and row.get("latency_ms") is None and j.get("latency_ms") is not None:
            row["latency_ms"] = j.get("latency_ms")
        snap = (
            a.get("request_snapshot")
            if isinstance(a.get("request_snapshot"), dict)
            else {}
        )
        if row.get("latency_ms") is None and isinstance(snap, dict):
            row["latency_ms"] = snap.get("pipeline_latency_ms")
        enriched.append(row)

    fills = [
        {
            "requested_price": (
                (a.get("request_snapshot") or {}).get("price")
                if isinstance(a.get("request_snapshot"), dict)
                else None
            ),
            "fill_price": a.get("price"),
            "slippage": None,
        }
        for a in enriched
        if str(a.get("outcome", "")).lower() == "success"
    ]
    for a, f in zip(enriched, fills, strict=False):
        j = by_req.get(str(a.get("request_id")))
        if j and j.get("slippage") is not None:
            f["slippage"] = j.get("slippage")

    analytics = compute_execution_analytics(attempts=enriched, fills=fills)
    metrics = dict(analytics.get("metrics") or {})
    # Explicit institutional KPIs
    total = len(enriched)
    successes = sum(
        1
        for a in enriched
        if str(a.get("outcome", "")).lower() in {"success", "filled"}
    )
    rejects = sum(
        1
        for a in enriched
        if str(a.get("outcome", "")).lower() in {"failed", "rejected", "disabled"}
    )
    cancelled = sum(
        1 for a in enriched if str(a.get("outcome", "")).lower() == "cancelled"
    )
    metrics["rejected_orders"] = rejects
    metrics["cancelled_orders"] = cancelled
    metrics["success_rate"] = round(successes / total, 4) if total else None
    metrics["fill_rate"] = metrics.get("fill_rate")
    metrics["average_slippage"] = metrics.get("average_slippage")
    metrics["latency_ms_avg"] = metrics.get("order_latency_ms_avg")
    metrics["execution_time_ms_avg"] = metrics.get(
        "order_duration_ms_avg"
    ) or metrics.get("order_latency_ms_avg")

    return ExecutionAnalyticsResponse(
        status=str(analytics.get("status") or "unavailable"),
        metrics=metrics,
        sample_sizes=dict(analytics.get("sample_sizes") or {}),
        data_source=str(analytics.get("data_source") or ""),
        journal_count=len(journal_rows),
    )
