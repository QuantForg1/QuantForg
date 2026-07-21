"""Opportunity ranking — execute only above configurable confidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_intelligence.config import MarketIntelligenceConfig


@dataclass(frozen=True, slots=True)
class OpportunityCandidate:
    signal_id: str
    strategy_id: str
    side: str
    confidence: Decimal
    score: Decimal | None = None  # optional caller-supplied rank score
    notes: str = ""


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    rank: int
    signal_id: str
    strategy_id: str
    side: str
    confidence: Decimal
    score: Decimal
    eligible: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "side": self.side,
            "confidence": str(self.confidence),
            "score": str(self.score),
            "eligible": self.eligible,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OpportunityRanking:
    ranked: tuple[RankedOpportunity, ...]
    eligible: tuple[RankedOpportunity, ...]
    threshold: Decimal
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ranked": [r.to_dict() for r in self.ranked],
            "eligible": [r.to_dict() for r in self.eligible],
            "threshold": str(self.threshold),
            "reasons": list(self.reasons),
        }


def rank_opportunities(
    config: MarketIntelligenceConfig,
    candidates: tuple[OpportunityCandidate, ...],
) -> OpportunityRanking:
    if not candidates:
        return OpportunityRanking(
            ranked=(),
            eligible=(),
            threshold=config.min_opportunity_score,
            reasons=("No candidate signals supplied — nothing to rank.",),
        )

    scored: list[tuple[Decimal, OpportunityCandidate]] = []
    for c in candidates:
        score = c.score if c.score is not None else c.confidence
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)

    ranked: list[RankedOpportunity] = []
    for i, (score, c) in enumerate(scored[: config.max_ranked_opportunities], start=1):
        eligible = score >= config.min_opportunity_score
        ranked.append(
            RankedOpportunity(
                rank=i,
                signal_id=c.signal_id,
                strategy_id=c.strategy_id,
                side=c.side,
                confidence=c.confidence,
                score=score.quantize(Decimal("0.01")),
                eligible=eligible,
                reason=(
                    f"Score {score} meets threshold {config.min_opportunity_score}"
                    if eligible
                    else f"Score {score} below threshold {config.min_opportunity_score}"
                ),
            )
        )

    eligible = tuple(r for r in ranked if r.eligible)
    reasons = [
        f"Ranked {len(ranked)} candidates; {len(eligible)} above "
        f"{config.min_opportunity_score}."
    ]
    if not eligible:
        reasons.append("No opportunities cleared the confidence threshold.")
    return OpportunityRanking(
        ranked=tuple(ranked),
        eligible=eligible,
        threshold=config.min_opportunity_score,
        reasons=tuple(reasons),
    )
