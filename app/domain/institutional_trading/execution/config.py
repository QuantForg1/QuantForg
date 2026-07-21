"""Phase C Execution Bridge configuration — separate from Phase A/B ITEConfig."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.execution.models import ExecutionMode
from app.domain.trading.gold_only import GOLD_SYMBOL

# Canary hard limits (operator LIVE promotion remains separate)
CANARY_MAX_LOTS = Decimal("0.01")
CANARY_MAX_OPEN_POSITIONS = 1


@dataclass(frozen=True, slots=True)
class ExecutionBridgeConfig:
    """Safe-bridge settings. Does not alter OMS or Phase A/B configs."""

    symbol: str = GOLD_SYMBOL
    config_version: str = "ite-exec-v1.0.0"

    # Decision freshness
    decision_ttl_seconds: int = 30

    # Modes: SHADOW (journal only) · CANARY_LIVE (max N/day) · LIVE
    mode: ExecutionMode = ExecutionMode.SHADOW

    canary_max_trades_per_day: int = 1
    canary_max_lots: Decimal = CANARY_MAX_LOTS
    canary_max_open_positions: int = CANARY_MAX_OPEN_POSITIONS

    # ITE magic / comment prefix for attribution
    magic: int = 260720
    comment_prefix: str = "ite:v1"

    # Re-verify spread gate (mirrors ITE reject threshold)
    max_spread_accept: Decimal = Decimal("2.00")

    # Slippage points passed to OMS intent
    slippage: int = 10

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "config_version": self.config_version,
            "decision_ttl_seconds": self.decision_ttl_seconds,
            "mode": self.mode.value,
            "canary_max_trades_per_day": self.canary_max_trades_per_day,
            "canary_max_lots": str(self.canary_max_lots),
            "canary_max_open_positions": self.canary_max_open_positions,
            "magic": self.magic,
            "comment_prefix": self.comment_prefix,
            "max_spread_accept": str(self.max_spread_accept),
            "slippage": self.slippage,
        }


DEFAULT_EXECUTION_BRIDGE_CONFIG = ExecutionBridgeConfig()
