"""Phase D — Institutional Position Management Engine (PME).

Manages EXISTING positions only. Never opens trades.
Does not modify OMS, Phase A, B, or C.
"""

from __future__ import annotations

from app.domain.institutional_trading.management.config import (
    DEFAULT_PME_CONFIG,
    PositionManagementConfig,
)
from app.domain.institutional_trading.management.engine import (
    PositionManagementEngine,
)
from app.domain.institutional_trading.management.journal import PositionManageJournal
from app.domain.institutional_trading.management.metrics import PositionManageMetrics
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    PositionLifecycleState,
    PositionManageContext,
    PositionManageRecord,
    VolatilityRegime,
)
from app.domain.institutional_trading.management.oms_port import OmsManagePort
from app.domain.institutional_trading.management.state_machine import (
    PositionStateMachine,
)

__all__ = [
    "DEFAULT_PME_CONFIG",
    "ManageActionKind",
    "ManageOutcome",
    "ManagedPosition",
    "OmsManagePort",
    "PositionLifecycleState",
    "PositionManageContext",
    "PositionManageJournal",
    "PositionManageMetrics",
    "PositionManageRecord",
    "PositionManagementConfig",
    "PositionManagementEngine",
    "PositionStateMachine",
    "VolatilityRegime",
]
