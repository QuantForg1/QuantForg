"""QuantForg AI Trading Robot V1 — capital-preservation orchestrator.

Never order_send. Never bypass Risk Engine or Safety Engine.
Never martingale / grid / average losers / increase risk after losses.
"""

from __future__ import annotations

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.ai_trading_robot.orchestrator import (
    RobotEvaluateInput,
    RobotV1Orchestrator,
)

__all__ = [
    "RobotEvaluateInput",
    "RobotV1Config",
    "RobotV1Orchestrator",
]
