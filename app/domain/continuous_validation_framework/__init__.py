"""Continuous Validation Framework (CVF) — validation layer (V2.2).

Completely read-only. Continuously validates that production trading remains
statistically consistent with historical research expectations.
Provides evidence only. Humans remain responsible for every production decision.
Never executes trades, modifies production, approves promotions, or triggers automation.
"""

from __future__ import annotations

from app.domain.continuous_validation_framework.platform import (
    ContinuousValidationFramework,
)

__all__ = ["ContinuousValidationFramework", "get_cvf"]

_CVF: ContinuousValidationFramework | None = None


def get_cvf() -> ContinuousValidationFramework:
    global _CVF
    if _CVF is None:
        _CVF = ContinuousValidationFramework()
    return _CVF
