"""Deterministic SCALP / HOLD / NO_TRADE classification.

Probability Center remains the only opportunity selector (threshold 70,
strong 85). This layer classifies a *already scored* candidate. It never
bypasses Risk, Safety, Portfolio, OMS, or reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
)

HOLD_MAX_OPEN_TRADES = 5
SCALP_MIN_BURST = 2
HOLD_MIN_BURST = 1

_HOLD_STRUCTURE_MIN = 70
_HOLD_RR_MIN = 1.30
_HOLD_MTF_MIN = 60
_HOLD_EXEC_MIN = 60
_HOLD_PILLARS_STRONG = 2
_HOLD_PILLARS_HIGH = 4

_TREND_REGIMES = frozenset(
    {
        "strong_trend",
        "trend",
        "weak_trend",
        "breakout",
        "expansion",
        "continuation",
    }
)


class TradeClass(StrEnum):
    SCALP = "SCALP"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True, slots=True)
class TradeClassification:
    trade_class: TradeClass
    reason: str
    opportunity_score: int
    direction: str
    confidence: int | None
    holding_pillars: tuple[str, ...]
    source: str = "trade_classifier"
    cycle_id: str | None = None
    snapshot_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_class": self.trade_class.value,
            "reason": self.reason,
            "opportunity_score": self.opportunity_score,
            "direction": self.direction,
            "confidence": self.confidence,
            "holding_pillars": list(self.holding_pillars),
            "source": self.source,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
        }


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def holding_pillars(
    *,
    structure: int | None,
    risk_reward: Any,
    regime: str | None,
    mtf_alignment: int | None,
    execution_quality: int | None,
) -> tuple[str, ...]:
    """Explainable HOLD evidence. Confidence alone is never sufficient."""
    found: list[str] = []
    if structure is not None and int(structure) >= _HOLD_STRUCTURE_MIN:
        found.append("structure")
    rr = _as_float(risk_reward)
    if rr is not None and rr >= _HOLD_RR_MIN:
        found.append("rr")
    regime_key = str(regime or "").strip().lower().replace("-", "_")
    if regime_key in _TREND_REGIMES:
        found.append("regime")
    if mtf_alignment is not None and int(mtf_alignment) >= _HOLD_MTF_MIN:
        found.append("mtf")
    if (
        execution_quality is not None
        and int(execution_quality) >= _HOLD_EXEC_MIN
    ):
        found.append("execution_quality")
    return tuple(found)


def classify_trade(
    *,
    opportunity_score: int,
    direction: str | None,
    confidence: int | None = None,
    structure: int | None = None,
    risk_reward: Any = None,
    regime: str | None = None,
    mtf_alignment: int | None = None,
    execution_quality: int | None = None,
    hard_market_invalid: bool = False,
    hard_invalid_reason: str | None = None,
    cycle_id: str | None = None,
    snapshot_id: str | None = None,
    threshold: int = OPPORTUNITY_SCORE_THRESHOLD,
    strong_threshold: int = STRONG_CANDIDATE_THRESHOLD,
) -> TradeClassification:
    """Classify one Probability Center verdict into SCALP / HOLD / NO_TRADE."""
    score = max(0, min(100, int(opportunity_score)))
    side = str(direction or "NONE").strip().upper() or "NONE"
    conf = _as_int(confidence)
    pillars = holding_pillars(
        structure=structure,
        risk_reward=risk_reward,
        regime=regime,
        mtf_alignment=mtf_alignment,
        execution_quality=execution_quality,
    )

    if hard_market_invalid:
        reason = hard_invalid_reason or (
            "Hard market invalidity — no trade."
        )
        return TradeClassification(
            trade_class=TradeClass.NO_TRADE,
            reason=reason,
            opportunity_score=score,
            direction=side,
            confidence=conf,
            holding_pillars=pillars,
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
        )
    if side not in {"BUY", "SELL"}:
        return TradeClassification(
            trade_class=TradeClass.NO_TRADE,
            reason="No tradeable direction (NONE).",
            opportunity_score=score,
            direction=side,
            confidence=conf,
            holding_pillars=pillars,
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
        )
    if score < int(threshold):
        return TradeClassification(
            trade_class=TradeClass.NO_TRADE,
            reason=(
                f"Insufficient opportunity "
                f"(score {score} < {int(threshold)})."
            ),
            opportunity_score=score,
            direction=side,
            confidence=conf,
            holding_pillars=pillars,
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
        )

    hold = (
        score >= int(strong_threshold) and len(pillars) >= _HOLD_PILLARS_STRONG
    ) or (score >= 80 and len(pillars) >= _HOLD_PILLARS_HIGH)

    if hold:
        return TradeClassification(
            trade_class=TradeClass.HOLD,
            reason=(
                "Opportunity score, structure, regime, RR and stability "
                "support holding."
            ),
            opportunity_score=score,
            direction=side,
            confidence=conf,
            holding_pillars=pillars,
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
        )

    return TradeClassification(
        trade_class=TradeClass.SCALP,
        reason=(
            "Opportunity is tradable but holding-quality evidence "
            "is insufficient."
        ),
        opportunity_score=score,
        direction=side,
        confidence=conf,
        holding_pillars=pillars,
        cycle_id=cycle_id,
        snapshot_id=snapshot_id,
    )
