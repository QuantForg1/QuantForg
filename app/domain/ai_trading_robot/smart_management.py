"""Smart trade management policy surface for Robot V1 (PME advisory).

Break-even, partial TP, and smart trailing stop are delegated to the
Position Management Engine. This module only exposes policy + validation —
it never places or modifies broker orders directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.ai_trading_robot.config import RobotV1Config


@dataclass(frozen=True, slots=True)
class SmartManagementPolicy:
    break_even_at_r: Decimal
    partial_tp_at_r: Decimal
    partial_tp_pct: Decimal
    trail_after_r: Decimal
    engine: str
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "break_even_at_r": str(self.break_even_at_r),
            "partial_tp_at_r": str(self.partial_tp_at_r),
            "partial_tp_pct": str(self.partial_tp_pct),
            "trail_after_r": str(self.trail_after_r),
            "engine": self.engine,
            "note": self.note,
            "features": [
                "break_even",
                "partial_tp",
                "smart_trailing_stop",
            ],
        }


def smart_management_policy(config: RobotV1Config) -> SmartManagementPolicy:
    return SmartManagementPolicy(
        break_even_at_r=config.break_even_at_r,
        partial_tp_at_r=config.partial_tp_at_r,
        partial_tp_pct=config.partial_tp_pct,
        trail_after_r=config.trail_after_r,
        engine="position_management_engine",
        note=(
            "Robot V1 configures PME advisory defaults only. "
            "SL/TP/partial/trail mutations go through the production PME "
            "and execution management path — never a direct broker shortcut."
        ),
    )
