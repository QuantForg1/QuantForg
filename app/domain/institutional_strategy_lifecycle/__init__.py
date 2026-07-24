"""Institutional Strategy Lifecycle Manager (ISLM) — V3.3 governance layer.

Completely isolated from production mutation. Tracks strategies from Draft
through Retirement with evidence. Lifecycle transitions require explicit
human approval. Never executes trades, changes parameters, auto-promotes,
or auto-retires.
"""

from __future__ import annotations

from app.domain.institutional_strategy_lifecycle.platform import (
    InstitutionalStrategyLifecycleManager,
)

__all__ = ["InstitutionalStrategyLifecycleManager", "get_islm"]

_ISLM: InstitutionalStrategyLifecycleManager | None = None


def get_islm() -> InstitutionalStrategyLifecycleManager:
    global _ISLM
    if _ISLM is None:
        _ISLM = InstitutionalStrategyLifecycleManager()
    return _ISLM
