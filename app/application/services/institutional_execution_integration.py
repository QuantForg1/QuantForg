"""Phase C integration façade — Decision → Execution Bridge → OMS port.

Does not modify Phase A/B pipelines or the Institutional OMS.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.decision_models import TradeDecision
from app.domain.institutional_trading.execution.bridge import ExecutionBridge
from app.domain.institutional_trading.execution.config import (
    DEFAULT_EXECUTION_BRIDGE_CONFIG,
    ExecutionBridgeConfig,
)
from app.domain.institutional_trading.execution.models import (
    ExecutionBridgeContext,
    ExecutionBridgeResult,
)
from app.domain.institutional_trading.execution.oms_port import OmsSubmitPort


@dataclass
class InstitutionalExecutionIntegration:
    """Single entry for Phase C: only BUY/SELL decisions may reach OMS."""

    bridge: ExecutionBridge

    @classmethod
    def create(
        cls,
        oms: OmsSubmitPort,
        *,
        config: ExecutionBridgeConfig | None = None,
    ) -> InstitutionalExecutionIntegration:
        return cls(
            bridge=ExecutionBridge(
                oms=oms,
                config=config or DEFAULT_EXECUTION_BRIDGE_CONFIG,
            )
        )

    def execute(
        self,
        decision: TradeDecision,
        context: ExecutionBridgeContext,
    ) -> ExecutionBridgeResult:
        """Forward decision through the bridge. Never bypasses eligibility/OMS."""
        return self.bridge.handle(decision, context)
