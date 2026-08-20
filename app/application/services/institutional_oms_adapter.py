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
        import time

        t0 = time.perf_counter()
        payload: dict[str, Any] = {}
        try:
            payload = {
                "user_id": str(user_id),
                "request_id": request_id,
                "intent": (
                    intent.to_dict() if hasattr(intent, "to_dict") else str(intent)
                ),
                "connected": bool(
                    connected if connected is not None else self.connected
                ),
                "login": login if login is not None else self.login,
            }
        except Exception:
            payload = {"request_id": request_id}
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
        result = map_pipeline_to_oms_result(pipeline)
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                record_oms,
            )
            from core.logging import get_logger as _get_logger

            response: dict[str, Any]
            if hasattr(result, "to_dict") and callable(result.to_dict):
                response = dict(result.to_dict())
            else:
                response = {
                    "outcome": getattr(result, "outcome", None),
                    "message": getattr(result, "message", None),
                    "retcode": getattr(result, "retcode", None),
                    "order_ticket": getattr(result, "order_ticket", None),
                    "deal_ticket": getattr(result, "deal_ticket", None),
                    "oms_status": getattr(result, "oms_status", None),
                    "gateway_status": getattr(result, "gateway_status", None),
                    "latency_ms": getattr(result, "latency_ms", None),
                    "retryable": getattr(result, "retryable", None),
                }
            record_oms(
                payload=payload,
                response=response,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                retry_count=0,
            )
        except Exception:
            try:
                from core.logging import get_logger as _get_logger

                _get_logger(__name__).exception("pvm_oms_adapter_record_failed")
            except Exception:  # noqa: S110
                pass
        return result


def pipeline_reach_flags(pipeline: PipelineResult) -> dict[str, bool]:
    """Which broker APIs this pipeline actually invoked."""
    order_check_reached = False
    order_send_reached = False
    for stage in pipeline.stages:
        name = str(getattr(getattr(stage, "stage", None), "value", stage.stage) or "")
        lower = name.lower()
        meta = getattr(stage, "meta", None) or {}
        if "validation" in lower and meta.get("order_check_retcode") is not None:
            order_check_reached = True
        if lower == "broker submission" or "broker submission" in lower:
            order_send_reached = True
    return {
        "oms_reached": True,
        "gateway_reached": order_check_reached or order_send_reached,
        "order_check_reached": order_check_reached,
        "order_send_reached": order_send_reached,
    }


def map_pipeline_to_oms_result(pipeline: PipelineResult) -> OmsSubmitResult:
    """Map OMS PipelineResult → bridge OmsSubmitResult (read-only mapping)."""
    exec_res = pipeline.execution_result
    reach = pipeline_reach_flags(pipeline)
    order_ticket = exec_res.order_ticket if exec_res else None
    deal_ticket = exec_res.deal_ticket if exec_res else None
    retryable = bool(exec_res.retryable) if exec_res else False

    # order_check TRADE_RETCODE_DONE is 0. That is not an order_send result.
    retcode: int | None
    if exec_res is not None and reach["order_send_reached"]:
        retcode = exec_res.retcode
    else:
        retcode = None

    gateway_status = "not_called"
    if reach["order_send_reached"]:
        gateway_status = "order_send"
    elif reach["order_check_reached"]:
        gateway_status = "order_check_only"
    for stage in pipeline.stages:
        name = getattr(stage, "stage", None)
        stage_name = str(getattr(name, "value", name or ""))
        if "broker submission" in stage_name.lower():
            gateway_status = str(
                getattr(stage, "status", gateway_status) or gateway_status
            )

    outcome = (pipeline.outcome or "").lower()
    raw = pipeline.to_dict() if hasattr(pipeline, "to_dict") else {}
    if isinstance(raw, dict):
        raw = {**raw, **reach}
    return OmsSubmitResult(
        outcome=outcome,
        message=pipeline.message or "",
        retcode=retcode,
        order_ticket=order_ticket,
        deal_ticket=deal_ticket,
        oms_status=outcome,
        gateway_status=str(gateway_status),
        latency_ms=float(pipeline.latency_ms or 0.0),
        retryable=retryable,
        raw=raw if isinstance(raw, dict) else {},
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
