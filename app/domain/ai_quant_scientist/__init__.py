"""AI Quant Scientist (AQS) — institutional AI research system (V2).

Completely read-only toward production. Produces recommendations only.
Never modifies strategy, risk, safety, OMS, gateway, thresholds, or
executes trades. Humans remain responsible for every decision.
"""

from __future__ import annotations

from app.domain.ai_quant_scientist.platform import AiQuantScientist

__all__ = ["AiQuantScientist", "get_aqs"]

_AQS: AiQuantScientist | None = None


def get_aqs() -> AiQuantScientist:
    global _AQS
    if _AQS is None:
        _AQS = AiQuantScientist()
    return _AQS
