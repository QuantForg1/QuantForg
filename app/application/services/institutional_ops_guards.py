"""Guarded OMS ports — Phase F wrappers; do not modify Phase C/D/OMS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
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
        return self.inner.submit_market(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
        )


@dataclass
class GuardedOmsManagePort:
    """Blocks PME modifications when kill switch armed."""

    inner: Any  # OmsManagePort
    plane: OperationsControlPlane

    def modify_sltp(self, **kwargs: Any) -> OmsManageResult:
        if not self.plane.pme_modifications_allowed():
            return OmsManageResult(
                outcome="disabled",
                message="Ops kill switch armed — PME modifications blocked",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
            )
        return self.inner.modify_sltp(**kwargs)

    def partial_close(self, **kwargs: Any) -> OmsManageResult:
        if not self.plane.pme_modifications_allowed():
            return OmsManageResult(
                outcome="disabled",
                message="Ops kill switch armed — PME modifications blocked",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
            )
        return self.inner.partial_close(**kwargs)

    def close_position(self, **kwargs: Any) -> OmsManageResult:
        # Flatten during emergency still allowed? Spec: PME stops sending modifications.
        # Close is a modification — block under kill switch.
        if not self.plane.pme_modifications_allowed():
            return OmsManageResult(
                outcome="disabled",
                message="Ops kill switch armed — PME close blocked",
                retcode=90001,
                oms_status="blocked",
                gateway_status="not_called",
            )
        return self.inner.close_position(**kwargs)
