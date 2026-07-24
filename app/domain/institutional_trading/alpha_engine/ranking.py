"""Opportunity ranking — Opportunity Score 0–100 per symbol."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    InstitutionalAlphaConfig,
)


@dataclass(frozen=True, slots=True)
class SymbolOpportunity:
    symbol: str
    opportunity_score: int
    ai_confidence: int
    trend_strength: int
    momentum: int
    liquidity: int
    volatility: int
    spread_score: int
    expected_rr: Decimal
    session_score: int
    direction: str
    reasons: tuple[str, ...]
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "opportunity_score": self.opportunity_score,
            "ai_confidence": self.ai_confidence,
            "trend_strength": self.trend_strength,
            "momentum": self.momentum,
            "liquidity": self.liquidity,
            "volatility": self.volatility,
            "spread_score": self.spread_score,
            "expected_rr": str(self.expected_rr),
            "session_score": self.session_score,
            "direction": self.direction,
            "reasons": list(self.reasons),
            "rank": self.rank,
        }


def _clamp(n: int) -> int:
    return max(0, min(100, int(n)))


def score_opportunity(
    *,
    symbol: str,
    ai_confidence: int,
    trend_strength: int,
    momentum: int,
    liquidity: int,
    volatility: int,
    spread_score: int,
    expected_rr: Decimal | float | str | None,
    session_score: int,
    direction: str = "NONE",
    reasons: tuple[str, ...] = (),
    config: InstitutionalAlphaConfig | None = None,
) -> SymbolOpportunity:
    cfg = config or DEFAULT_ALPHA_CONFIG
    rr = Decimal("0")
    if expected_rr is not None:
        try:
            rr = Decimal(str(expected_rr))
        except Exception:
            rr = Decimal("0")
    # Map RR 0–3 → 0–100
    rr_score = _clamp(int(float(min(rr, Decimal("3"))) / 3.0 * 100))

    weights = {
        "confidence": cfg.w_confidence,
        "trend": cfg.w_trend,
        "momentum": cfg.w_momentum,
        "liquidity": cfg.w_liquidity,
        "volatility": cfg.w_volatility,
        "spread": cfg.w_spread,
        "expected_rr": cfg.w_expected_rr,
        "session": cfg.w_session,
    }
    # Continuous learning — gradual multipliers only; never overwrite base rules.
    try:
        from app.domain.institutional_trading.production_hardening.learning import (
            get_learning_weight_store,
        )

        weights = get_learning_weight_store().apply_to_weights(weights)
    except Exception:
        pass
    factors = {
        "confidence": _clamp(ai_confidence),
        "trend": _clamp(trend_strength),
        "momentum": _clamp(momentum),
        "liquidity": _clamp(liquidity),
        "volatility": _clamp(volatility),
        "spread": _clamp(spread_score),
        "expected_rr": rr_score,
        "session": _clamp(session_score),
    }
    total_w = sum(weights.values()) or 1
    weighted = sum(factors[k] * weights[k] for k in weights)
    score = _clamp(round(weighted / total_w))

    return SymbolOpportunity(
        symbol=symbol.upper(),
        opportunity_score=score,
        ai_confidence=_clamp(ai_confidence),
        trend_strength=_clamp(trend_strength),
        momentum=_clamp(momentum),
        liquidity=_clamp(liquidity),
        volatility=_clamp(volatility),
        spread_score=_clamp(spread_score),
        expected_rr=rr,
        session_score=_clamp(session_score),
        direction=(direction or "NONE").upper(),
        reasons=reasons,
    )


def rank_opportunities(
    opportunities: list[SymbolOpportunity],
    *,
    config: InstitutionalAlphaConfig | None = None,
) -> list[SymbolOpportunity]:
    """Sort highest Opportunity Score first; stamp rank 1..N."""
    cfg = config or DEFAULT_ALPHA_CONFIG
    ordered = sorted(
        opportunities,
        key=lambda o: (o.opportunity_score, o.ai_confidence, o.expected_rr),
        reverse=True,
    )
    out: list[SymbolOpportunity] = []
    for i, opp in enumerate(ordered, start=1):
        out.append(
            SymbolOpportunity(
                symbol=opp.symbol,
                opportunity_score=opp.opportunity_score,
                ai_confidence=opp.ai_confidence,
                trend_strength=opp.trend_strength,
                momentum=opp.momentum,
                liquidity=opp.liquidity,
                volatility=opp.volatility,
                spread_score=opp.spread_score,
                expected_rr=opp.expected_rr,
                session_score=opp.session_score,
                direction=opp.direction,
                reasons=opp.reasons,
                rank=i,
            )
        )
    # Filter below floor for execution candidates (ranking still returned full list by caller)
    _ = cfg
    return out


def top_executable(
    ranked: list[SymbolOpportunity],
    *,
    config: InstitutionalAlphaConfig | None = None,
) -> list[SymbolOpportunity]:
    cfg = config or DEFAULT_ALPHA_CONFIG
    eligible = [
        o
        for o in ranked
        if o.opportunity_score >= cfg.min_opportunity_score
        and o.direction in {"BUY", "SELL"}
    ]
    return eligible[: max(1, cfg.execute_top_n)]
