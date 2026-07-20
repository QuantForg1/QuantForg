"""Adapter: Institutional OMS submit without modifying the OMS.

Wraps ``InstitutionalExecutionEngine.run_submit`` / optional use-case path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    PipelineResult,
)
from app.domain.entities.mt5_order import OrderIntent
from app.domain.institutional_trading.execution.models import OmsSubmitResult


@dataclass
class InstitutionalOmsAdapter:
    """OmsSubmitPort implementation — delegates to existing OMS only."""

    engine: InstitutionalExecutionEngine
    connected: bool = True
    login: int | None = None

    def submit_market(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
    ) -> OmsSubmitResult:
        pipeline, _decision = self.engine.run_submit(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected if connected is not None else self.connected,
            login=login if login is not None else self.login,
            recent_decisions=[],
            existing_decision=None,
            skip_broker=False,
            action="submit",
        )
        return map_pipeline_to_oms_result(pipeline)


def map_pipeline_to_oms_result(pipeline: PipelineResult) -> OmsSubmitResult:
    """Map OMS PipelineResult → bridge OmsSubmitResult (read-only mapping)."""
    exec_res = pipeline.execution_result
    retcode = exec_res.retcode if exec_res else 0
    order_ticket = exec_res.order_ticket if exec_res else None
    deal_ticket = exec_res.deal_ticket if exec_res else None
    retryable = bool(exec_res.retryable) if exec_res else False

    gateway_status = "unknown"
    for stage in pipeline.stages:
        name = getattr(stage, "stage", None)
        stage_name = name.value if hasattr(name, "value") else str(name or "")
        if "broker" in stage_name.lower() or "gateway" in stage_name.lower():
            gateway_status = getattr(stage, "status", gateway_status)

    outcome = (pipeline.outcome or "").lower()
    return OmsSubmitResult(
        outcome=outcome,
        message=pipeline.message or "",
        retcode=int(retcode or 0),
        order_ticket=order_ticket,
        deal_ticket=deal_ticket,
        oms_status=outcome,
        gateway_status=str(gateway_status),
        latency_ms=float(pipeline.latency_ms or 0.0),
        retryable=retryable,
        raw=pipeline.to_dict() if hasattr(pipeline, "to_dict") else {},
    )


class RecordingOmsPort:
    """Test / shadow double — records intents; never touches real OMS."""

    def __init__(
        self,
        result: OmsSubmitResult | None = None,
        *,
        fail_as: str = "failed",
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result or OmsSubmitResult(
            outcome="success",
            message="ok",
            retcode=10009,
            order_ticket=1001,
            deal_ticket=2001,
            oms_status="success",
            gateway_status="ok",
            latency_ms=12.0,
            retryable=False,
        )
        self._fail_as = fail_as
        self.fail_next = False

    def submit_market(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
    ) -> OmsSubmitResult:
        self.calls.append(
            {
                "user_id": user_id,
                "request_id": request_id,
                "intent": intent.to_dict(),
                "connected": connected,
                "login": login,
            }
        )
        if self.fail_next:
            self.fail_next = False
            outcome = self._fail_as
            return OmsSubmitResult(
                outcome=outcome,
                message=f"forced {outcome}",
                retcode=10006 if outcome == "rejected" else 10031,
                oms_status=outcome,
                gateway_status="failed" if outcome == "gateway_failure" else "ok",
                retryable=False,
            )
        return self.result
