"""Live Performance Lab v8 — config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PerformanceLabConfig:
    version: str = "performance-lab-v8.0.0"

    # Champion = production; Challenger = candidate weights only (never executes)
    challenger_enabled: bool = True
    challenger_may_execute: bool = False  # HARD LOCK — never flip without evidence + human gate

    # Challenger weight tilt vs champion (candidate scoring profile)
    challenger_weight_tilt: dict[str, float] | None = None

    max_duels: int = 5_000
    max_opportunities: int = 10_000
    max_replays: int = 2_000
    max_recommendations: int = 200
    calibration_bins: tuple[int, ...] = (50, 60, 70, 75, 80, 85, 90, 95)

    overconfidence_gap: float = 8.0  # predicted - actual
    underconfidence_gap: float = -8.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "challenger_enabled": self.challenger_enabled,
            "challenger_may_execute": self.challenger_may_execute,
            "max_duels": self.max_duels,
            "note": "Challenger never places orders. Recommendations never auto-apply.",
        }


DEFAULT_LAB_CONFIG = PerformanceLabConfig()

# Candidate scoring profile — different from production champion multipliers
DEFAULT_CHALLENGER_TILT: dict[str, float] = {
    "trend": 1.12,
    "momentum": 1.08,
    "liquidity": 0.92,
    "volatility": 0.88,
    "session": 1.05,
    "bos": 1.15,
    "choch": 1.10,
    "fvg": 1.05,
    "order_block": 1.10,
}
