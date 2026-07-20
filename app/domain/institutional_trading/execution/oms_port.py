"""OMS submit port — bridge talks only through this; OMS implementation unchanged."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.mt5_order import OrderIntent
from app.domain.institutional_trading.execution.models import OmsSubmitResult


class OmsSubmitPort(Protocol):
    """Thin port over Institutional OMS submit.

    Implementations must not invent fills.
    """

    def submit_market(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
    ) -> OmsSubmitResult:
        """Forward a market OrderIntent to the existing Institutional OMS."""
        ...
