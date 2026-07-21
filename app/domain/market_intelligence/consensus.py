"""Strategy consensus — combine enabled strategy outputs; reject conflicts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_intelligence.config import MarketIntelligenceConfig


@dataclass(frozen=True, slots=True)
class StrategySignal:
    strategy_id: str
    enabled: bool
    side: str  # buy | sell | flat
    confidence: Decimal
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    accepted: bool
    side: str | None
    confidence: Decimal
    agreeing: tuple[str, ...]
    dissenting: tuple[str, ...]
    conflict: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "side": self.side,
            "confidence": str(self.confidence),
            "agreeing": list(self.agreeing),
            "dissenting": list(self.dissenting),
            "conflict": self.conflict,
            "reasons": list(self.reasons),
        }


def build_strategy_consensus(
    config: MarketIntelligenceConfig, signals: tuple[StrategySignal, ...]
) -> ConsensusResult:
    enabled = [s for s in signals if s.enabled and s.side.lower() in {"buy", "sell"}]
    if not enabled:
        return ConsensusResult(
            accepted=False,
            side=None,
            confidence=Decimal("0"),
            agreeing=(),
            dissenting=(),
            conflict=False,
            reasons=("No enabled directional strategy signals supplied.",),
        )

    buys = [s for s in enabled if s.side.lower() == "buy"]
    sells = [s for s in enabled if s.side.lower() == "sell"]
    conflict = bool(buys) and bool(sells)
    reasons: list[str] = []

    if conflict and config.reject_conflicts:
        return ConsensusResult(
            accepted=False,
            side=None,
            confidence=Decimal("0"),
            agreeing=(),
            dissenting=tuple(s.strategy_id for s in enabled),
            conflict=True,
            reasons=(
                "Conflicting buy/sell signals among enabled strategies — rejected.",
            ),
        )

    majority = buys if len(buys) >= len(sells) else sells
    side = majority[0].side.lower()
    agreeing_ids = tuple(s.strategy_id for s in majority)
    dissenting_ids = tuple(
        s.strategy_id for s in enabled if s.side.lower() != side
    )

    if len(majority) < config.min_agreeing_strategies:
        reasons.append(
            f"Only {len(majority)} agreeing strategies; need "
            f"{config.min_agreeing_strategies}."
        )
        return ConsensusResult(
            accepted=False,
            side=side,
            confidence=Decimal("0"),
            agreeing=agreeing_ids,
            dissenting=dissenting_ids,
            conflict=conflict,
            reasons=tuple(reasons),
        )

    avg = (
        sum((s.confidence for s in majority), Decimal("0")) / Decimal(len(majority))
    ).quantize(Decimal("0.01"))
    if avg < config.min_consensus_confidence:
        reasons.append(
            f"Consensus confidence {avg} below "
            f"{config.min_consensus_confidence}."
        )
        return ConsensusResult(
            accepted=False,
            side=side,
            confidence=avg,
            agreeing=agreeing_ids,
            dissenting=dissenting_ids,
            conflict=conflict,
            reasons=tuple(reasons),
        )

    reasons.append(
        f"Consensus {side.upper()} from {len(majority)} strategies "
        f"(confidence {avg})."
    )
    return ConsensusResult(
        accepted=True,
        side=side,
        confidence=avg,
        agreeing=agreeing_ids,
        dissenting=dissenting_ids,
        conflict=conflict,
        reasons=tuple(reasons),
    )
