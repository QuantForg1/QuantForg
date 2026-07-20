"""Phase D façade — Position Management Engine entry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.management.config import (
    DEFAULT_PME_CONFIG,
    PositionManagementConfig,
)
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    PositionManageContext,
    PositionManageResult,
)
from app.domain.institutional_trading.management.oms_port import OmsManagePort


@dataclass
class InstitutionalPositionManagement:
    """Sole Phase D entry: register fills, evaluate open positions."""

    engine: PositionManagementEngine
    ops_plane: Any | None = None

    @classmethod
    def create(
        cls,
        oms: OmsManagePort,
        *,
        config: PositionManagementConfig | None = None,
        ops_plane: Any | None = None,
    ) -> InstitutionalPositionManagement:
        return cls(
            engine=PositionManagementEngine(
                oms=oms,
                config=config or DEFAULT_PME_CONFIG,
            ),
            ops_plane=ops_plane,
        )

    def register(self, position: ManagedPosition) -> ManagedPosition:
        return self.engine.register(position)

    def evaluate(
        self, ticket: int, context: PositionManageContext
    ) -> PositionManageResult:
        # Shared kill switch: ops plane is source of truth when bound
        if self.ops_plane is not None and (
            bool(self.ops_plane.kill_switch_armed) != context.kill_switch_armed
            or bool(self.ops_plane.daily_loss_exceeded) != context.daily_loss_exceeded
        ):
            context = PositionManageContext(
                now=context.now,
                current_price=context.current_price,
                atr=context.atr,
                mid_price=context.mid_price,
                spread=context.spread,
                market_open=context.market_open,
                connection_stable=context.connection_stable,
                structure_broken=context.structure_broken,
                trend_reversed=context.trend_reversed,
                risk_requests_exit=context.risk_requests_exit,
                daily_loss_exceeded=bool(self.ops_plane.daily_loss_exceeded),
                kill_switch_armed=bool(self.ops_plane.kill_switch_armed),
                news_requests_exit=context.news_requests_exit,
                position_still_open=context.position_still_open,
                book_volume=context.book_volume,
                book_stop=context.book_stop,
                user_id=context.user_id,
                request_id=context.request_id,
                connected=context.connected,
                login=context.login,
            )
        return self.engine.evaluate(ticket, context)
