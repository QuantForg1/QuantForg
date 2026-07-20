"""Adapter: Institutional OMS manage without modifying the OMS.

Wraps ``parse_order_intent`` + ``InstitutionalExecutionEngine.run_submit``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.domain.institutional_trading.management.models import OmsManageResult


def _map_pipeline(pipeline: Any) -> OmsManageResult:
    exec_res = getattr(pipeline, "execution_result", None)
    retcode = exec_res.retcode if exec_res else 0
    outcome = (getattr(pipeline, "outcome", None) or "").lower()
    gateway_status = "unknown"
    for stage in getattr(pipeline, "stages", []) or []:
        name = getattr(stage, "stage", None)
        stage_name = name.value if hasattr(name, "value") else str(name or "")
        if "broker" in stage_name.lower() or "gateway" in stage_name.lower():
            gateway_status = getattr(stage, "status", gateway_status)
    return OmsManageResult(
        outcome=outcome,
        message=getattr(pipeline, "message", "") or "",
        retcode=int(retcode or 0),
        order_ticket=exec_res.order_ticket if exec_res else None,
        deal_ticket=exec_res.deal_ticket if exec_res else None,
        latency_ms=float(getattr(pipeline, "latency_ms", 0.0) or 0.0),
        gateway_status=str(gateway_status),
        oms_status=outcome,
    )


@dataclass
class InstitutionalOmsManageAdapter:
    """OmsManagePort → existing InstitutionalExecutionEngine.run_submit."""

    engine: InstitutionalExecutionEngine

    def modify_sltp(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        stop_loss: Decimal,
        take_profit: Decimal | None,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        intent = parse_order_intent(
            symbol=symbol,
            side=side,
            order_type="market",
            volume="0.01",
            stop_loss=str(stop_loss),
            take_profit=str(take_profit) if take_profit is not None else None,
            comment=comment,
            position=position,
            oms_kind="sltp",
        )
        pipeline, _ = self.engine.run_submit(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent_decisions=[],
            action="manage",
        )
        return _map_pipeline(pipeline)

    def partial_close(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        volume: Decimal,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        intent = parse_order_intent(
            symbol=symbol,
            side=side,
            order_type="market",
            volume=str(volume),
            comment=comment,
            position=position,
            oms_kind="partial_close",
        )
        pipeline, _ = self.engine.run_submit(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent_decisions=[],
            action="manage",
        )
        return _map_pipeline(pipeline)

    def close_position(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        volume: Decimal,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        intent = parse_order_intent(
            symbol=symbol,
            side=side,
            order_type="market",
            volume=str(volume),
            comment=comment,
            position=position,
            oms_kind="close",
        )
        pipeline, _ = self.engine.run_submit(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent_decisions=[],
            action="manage",
        )
        return _map_pipeline(pipeline)


class RecordingOmsManagePort:
    """Test double — records manage calls; never touches real OMS."""

    def __init__(
        self,
        result: OmsManageResult | None = None,
        *,
        fail_as: str = "failed",
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result or OmsManageResult(
            outcome="success",
            message="ok",
            retcode=10009,
            order_ticket=1,
            deal_ticket=2,
            latency_ms=5.0,
            gateway_status="ok",
            oms_status="success",
        )
        self._fail_as = fail_as
        self.fail_next = False

    def _maybe_fail(self) -> OmsManageResult:
        if self.fail_next:
            self.fail_next = False
            outcome = self._fail_as
            return OmsManageResult(
                outcome=outcome,
                message=f"forced {outcome}",
                retcode=10031 if "gateway" in outcome else 10016,
                gateway_status="failed" if "gateway" in outcome else "ok",
                oms_status=outcome,
            )
        return self.result

    def modify_sltp(self, **kwargs: Any) -> OmsManageResult:
        self.calls.append({"method": "modify_sltp", **kwargs})
        return self._maybe_fail()

    def partial_close(self, **kwargs: Any) -> OmsManageResult:
        self.calls.append({"method": "partial_close", **kwargs})
        return self._maybe_fail()

    def close_position(self, **kwargs: Any) -> OmsManageResult:
        self.calls.append({"method": "close_position", **kwargs})
        return self._maybe_fail()
