"""Walk-Forward Validation enumerations — offline only, never live trading."""

from __future__ import annotations

from enum import StrEnum


class WalkForwardStatus(StrEnum):
    """Lifecycle of a walk-forward validation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PromotionDecision(StrEnum):
    """Promotion gate between backtesting and paper trading."""

    PROMOTE_TO_PAPER = "promote_to_paper"
    NEEDS_REWORK = "needs_rework"
    REJECT = "reject"
