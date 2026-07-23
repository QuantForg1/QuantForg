"""AI Quant Copilot (AQC) — institutional AI operations assistant (V2).

Strictly read-only toward production. Provides explanations, investigations,
and evidence only. Never executes trades or modifies strategy, thresholds,
risk, safety, OMS, gateway, scheduler, research, or production data.
Humans make all operational decisions.
"""

from __future__ import annotations

from app.domain.ai_quant_copilot.platform import AiQuantCopilot

__all__ = ["AiQuantCopilot", "get_aqc"]

_AQC: AiQuantCopilot | None = None


def get_aqc() -> AiQuantCopilot:
    global _AQC
    if _AQC is None:
        _AQC = AiQuantCopilot()
    return _AQC
