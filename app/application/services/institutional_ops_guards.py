"""Guarded OMS ports — Phase F wrappers; do not modify Phase C/D/OMS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from app.domain.entities.mt5_order import OrderIntent
from app.domain.institutional_trading.execution.models import OmsSubmitResult
from app.domain.institutional_trading.management.models import OmsManageResult
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)


@dataclass
class GuardedOmsSubmitPort:
    """Blocks OMS submits when kill switch armed or mode is SHADOW."""

    inner: Any  # OmsSubmitPort
    plane: OperationsControlPlane

    def submit_market(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
    ) -> OmsSubmitResult:
        if not self.plane.oms_orders_allowed():
            reason = (
                "kill switch armed"
                if self.plane.kill_switch_armed
                else f"mode={self.plane.mode.value}"
            )
            return OmsSubmitResult(
                outcome="disabled",
                message=f"Ops control plane blocked OMS submit ({reason})",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
                retryable=False,
            )
        from app.application.services.account_execution_gate import (
            submit_blocked_reason,
        )

        mismatch = submit_blocked_reason(user_id=user_id, login=login)
        if mismatch is not None:
            return OmsSubmitResult(
                outcome="disabled",
                message="ACCOUNT_SESSION_MISMATCH — OMS not called",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
                retryable=False,
            )
        return cast(
            "OmsSubmitResult",
            self.inner.submit_market(
                user_id=user_id,
                request_id=request_id,
                intent=intent,
                connected=connected,
                login=login,
            ),
        )


def _sl_tightens(kwargs: dict[str, Any]) -> bool:
    """True when the new SL moves toward price and the TP is left unchanged."""
    from decimal import Decimal

    current = kwargs.get("current_stop_loss")
    new = kwargs.get("stop_loss")
    if current is None or new is None or kwargs.get("take_profit_changed"):
        return False
    cur, nxt = Decimal(str(current)), Decimal(str(new))
    if cur <= 0 or nxt <= 0:
        return False
    side = str(kwargs.get("side") or "").strip().lower()
    if side == "buy":
        return nxt > cur
    if side == "sell":
        return nxt < cur
    return False


@dataclass
class GuardedOmsManagePort:
    """Kill switch / Phase A halt block every risk-adding PME action.

    Closes, partial closes and provable SL tightening are always allowed
    (owner decision 2026-10-20).
    """

    inner: Any  # OmsManagePort
    plane: OperationsControlPlane

    def modify_sltp(self, **kwargs: Any) -> OmsManageResult:
        if not self.plane.pme_modifications_allowed() and not (
            self.plane.pme_protective_allowed() and _sl_tightens(kwargs)
        ):
            return OmsManageResult(
                outcome="disabled",
                message="Ops kill switch armed — only SL tightening is allowed",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
            )
        return cast("OmsManageResult", self.inner.modify_sltp(**kwargs))

    def partial_close(self, **kwargs: Any) -> OmsManageResult:
        # Reducing size is protective — never blocked by the kill switch.
        return cast("OmsManageResult", self.inner.partial_close(**kwargs))

    def close_position(self, **kwargs: Any) -> OmsManageResult:
        # Flattening is protective — never blocked by the kill switch.
        return cast("OmsManageResult", self.inner.close_position(**kwargs))
