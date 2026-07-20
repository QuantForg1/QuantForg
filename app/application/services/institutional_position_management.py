"""Phase D façade — Position Management Engine entry."""

from __future__ import annotations

from dataclasses import dataclass

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

    @classmethod
    def create(
        cls,
        oms: OmsManagePort,
        *,
        config: PositionManagementConfig | None = None,
    ) -> InstitutionalPositionManagement:
        return cls(
            engine=PositionManagementEngine(
                oms=oms,
                config=config or DEFAULT_PME_CONFIG,
            )
        )

    def register(self, position: ManagedPosition) -> ManagedPosition:
        return self.engine.register(position)

    def evaluate(
        self, ticket: int, context: PositionManageContext
    ) -> PositionManageResult:
        return self.engine.evaluate(ticket, context)
