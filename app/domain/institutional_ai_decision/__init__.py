"""QuantForg Institutional AI Decision Engine V1.

Capital preservation and disciplined execution decisions.
Never order_send. Never bypass Risk Engine or Safety Engine.
Never martingale / grid / average-down. Never promise profitability.
"""

from __future__ import annotations

from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.institutional_ai_decision.orchestrator import (
    DecisionEngineV1,
    DecisionEvaluateInput,
    DecisionEvaluateResult,
)

__all__ = [
    "DecisionEngineV1",
    "DecisionEngineV1Config",
    "DecisionEvaluateInput",
    "DecisionEvaluateResult",
]
