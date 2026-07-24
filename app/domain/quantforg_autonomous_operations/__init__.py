"""QuantForg Autonomous Operations Center (AOC) — V6 operational orchestration.

Completely read-only. Aggregates platform evidence, prioritizes work, and
recommends operator actions. Never executes trades, modifies production,
approves releases, allocates capital, deploys strategies, or remediates
automatically. Human approval required for every recommendation.
"""

from __future__ import annotations

from app.domain.quantforg_autonomous_operations.platform import (
    QuantForgAutonomousOperationsCenter,
)

__all__ = ["QuantForgAutonomousOperationsCenter", "get_aoc"]

_AOC: QuantForgAutonomousOperationsCenter | None = None


def get_aoc() -> QuantForgAutonomousOperationsCenter:
    global _AOC
    if _AOC is None:
        _AOC = QuantForgAutonomousOperationsCenter()
    return _AOC
