"""OMS manage port — PME talks only through this; OMS implementation unchanged."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.domain.institutional_trading.management.models import OmsManageResult


class OmsManagePort(Protocol):
    """Thin port over Institutional OMS manage (SLTP / partial / close)."""

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
    ) -> OmsManageResult: ...

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
    ) -> OmsManageResult: ...

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
    ) -> OmsManageResult: ...
