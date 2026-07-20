"""Phase C — Execution Bridge between TradeDecision and Institutional OMS.

Never modifies OMS. Never bypasses Decision Engine or Eligibility.
No AI. No second execution path.
"""

from __future__ import annotations

from app.domain.institutional_trading.execution.bridge import ExecutionBridge
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.journal import ExecutionAttemptJournal
from app.domain.institutional_trading.execution.kill_switch import KillSwitch
from app.domain.institutional_trading.execution.metrics import ExecutionBridgeMetrics
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionAttemptRecord,
    ExecutionBridgeContext,
    ExecutionBridgeResult,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.execution.oms_port import OmsSubmitPort

__all__ = [
    "BridgeAbortReason",
    "ExecutionAttemptJournal",
    "ExecutionAttemptRecord",
    "ExecutionBridge",
    "ExecutionBridgeConfig",
    "ExecutionBridgeContext",
    "ExecutionBridgeMetrics",
    "ExecutionBridgeResult",
    "ExecutionMode",
    "KillSwitch",
    "OmsSubmitPort",
    "OmsSubmitResult",
]
