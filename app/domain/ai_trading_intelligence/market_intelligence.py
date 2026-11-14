"""Assemble explainable market intelligence from caller-supplied facts.

Never invents OHLC or liquidity. Missing factors are null/omitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.ai_trading_intelligence.regime import (
    RegimeAssessment,
    map_canonical_regime,
)

MODEL_VERSION = "phase4-ati-1.0.0"


@dataclass(frozen=True, slots=True)
class MarketIntelligenceBundle:
    symbol: str
    as_of: datetime
    regime: RegimeAssessment
    structure: dict[str, Any] | None
    trend: dict[str, Any] | None
    momentum: dict[str, Any] | None
    volatility: dict[str, Any] | None
    support_resistance: dict[str, Any] | None
    liquidity: dict[str, Any] | None
    price_action: dict[str, Any] | None
    session: dict[str, Any] | None
    multi_timeframe: dict[str, Any] | None
    confidence: Decimal
    data_sources: tuple[str, ...]
    model_version: str
    notes: tuple[str, ...]
    methodology: dict[str, Any] = field(default_factory=dict)


def _opt_dict(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict) and value:
        return dict(value)
    return None


def assemble_market_intelligence(
    *,
    symbol: str,
    facts: dict[str, Any] | None = None,
    as_of: datetime | None = None,
) -> MarketIntelligenceBundle:
    """Build a provenance-aware bundle from provided engine facts.

    Expected optional keys in ``facts`` (all optional — honesty over invention):
    regime_label, regime_confidence, structure, trend, momentum, volatility,
    support_resistance, liquidity, price_action, session, multi_timeframe,
    data_sources, confidence.
    """
    facts = facts or {}
    clock = as_of or datetime.now(UTC)
    sources = tuple(str(s) for s in (facts.get("data_sources") or []) if s)
    notes: list[str] = []

    regime = map_canonical_regime(
        (
            facts.get("regime_label")
            if isinstance(facts.get("regime_label"), str)
            else None
        ),
        confidence=facts.get("regime_confidence"),
    )

    liquidity = _opt_dict(facts.get("liquidity"))
    if liquidity is None:
        notes.append("liquidity_omitted_unavailable")

    momentum = _opt_dict(facts.get("momentum"))
    if momentum is None:
        notes.append("momentum_omitted_unavailable")

    conf_raw = facts.get("confidence")
    try:
        confidence = (
            Decimal(str(conf_raw)) if conf_raw is not None else regime.confidence
        )
    except Exception:
        confidence = regime.confidence

    if not sources:
        notes.append("no_data_sources_declared")
        sources = ("caller_facts",)

    return MarketIntelligenceBundle(
        symbol=(symbol or "").strip().upper() or "UNKNOWN",
        as_of=clock,
        regime=regime,
        structure=_opt_dict(facts.get("structure")),
        trend=_opt_dict(facts.get("trend")),
        momentum=momentum,
        volatility=_opt_dict(facts.get("volatility")),
        support_resistance=_opt_dict(facts.get("support_resistance")),
        liquidity=liquidity,
        price_action=_opt_dict(facts.get("price_action")),
        session=_opt_dict(facts.get("session")),
        multi_timeframe=_opt_dict(facts.get("multi_timeframe")),
        confidence=confidence,
        data_sources=sources,
        model_version=MODEL_VERSION,
        notes=tuple(notes),
        methodology={
            "assembly": "caller_supplied_facts_only",
            "invents_ohlc": False,
            "invents_liquidity": False,
            "regime": regime.methodology,
        },
    )
