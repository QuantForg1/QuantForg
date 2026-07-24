"""Reliability Engineering Suite (RES) — platform reliability layer (V2.1).

Completely read-only. Evaluates health, availability, resilience and recovery.
Never executes trades or modifies strategy, thresholds, risk, safety, OMS,
gateway, scheduler, or production data.
"""

from __future__ import annotations

from app.domain.reliability_engineering_suite.platform import ReliabilityEngineeringSuite

__all__ = ["ReliabilityEngineeringSuite", "get_res"]

_RES: ReliabilityEngineeringSuite | None = None


def get_res() -> ReliabilityEngineeringSuite:
    global _RES
    if _RES is None:
        _RES = ReliabilityEngineeringSuite()
    return _RES
