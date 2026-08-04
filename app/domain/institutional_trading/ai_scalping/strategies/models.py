"""Multi-strategy scalping pack — models.

All strategies inherit SCALPING_V1 safety floors. They never lower structure,
momentum, quality, or risk. They only specialize scoring / extra filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

StrategyId = Literal[
    "smc_scalping",
    "trend_continuation",
    "breakout_scalping",
    "range_mean_reversion",
    "momentum_scalping",
]


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: StrategyId
    name: str
    explanation: str
    # Soft weights for strategy_quality (sum need not be 100; normalized)
    weights: dict[str, float]
    # Extra filters — may only ADD requirements (never below SCALPING_V1)
    require_regimes: tuple[str, ...] = ()
    forbid_regimes: tuple[str, ...] = ()
    min_alignment: int = 0
    min_momentum: int = 0  # clamped to >= cfg.min_momentum_score at eval
    min_structure: int = 0  # clamped to >= cfg.min_structure_score at eval
    min_bos: int = 0
    min_volume: int = 0
    require_atr_band: tuple[str, ...] = ()  # high/normal/low
    prefer_setup_families: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    strategy_id: StrategyId
    name: str
    symbol: str
    direction: str
    passed: bool
    quality: int
    confidence: int
    explanation: str
    reject_reason: str | None
    filters: dict[str, bool]
    score_components: dict[str, int]
    live_rank_boost: float = 0.0

    @property
    def rank_key(self) -> tuple[float, int, int]:
        """Higher is better — quality primary, then confidence, then boost."""
        return (
            float(self.quality) + self.live_rank_boost,
            self.confidence,
            self.quality,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "symbol": self.symbol,
            "direction": self.direction,
            "passed": self.passed,
            "quality": self.quality,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "reject_reason": self.reject_reason,
            "filters": dict(self.filters),
            "score_components": dict(self.score_components),
            "live_rank_boost": self.live_rank_boost,
        }
