"""Unified signal quality product DTO — not a win-probability guarantee."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain.ai_trading_intelligence.regime import (
    CanonicalRegime,
    map_canonical_regime,
)


@dataclass(frozen=True, slots=True)
class SignalQualityScore:
    symbol: str
    direction: str | None
    strategy_source: str | None
    regime: CanonicalRegime
    confidence: Decimal
    quality: Decimal
    risk_assessment: str
    entry_context: dict[str, Any] | None
    sl_tp_context: dict[str, Any] | None
    supporting_factors: tuple[str, ...]
    conflicting_factors: tuple[str, ...]
    valid_until: datetime | None
    stale: bool
    actionable: bool
    explanation: str
    disclaimer: str
    methodology: dict[str, Any] = field(default_factory=dict)


_DISCLAIMER = (
    "Confidence and quality scores are relative model/engine outputs, "
    "not guaranteed probabilities of profit."
)


def score_signal_quality(
    *,
    symbol: str,
    direction: str | None = None,
    strategy_source: str | None = None,
    regime_label: str | None = None,
    regime_confidence: Decimal | float | int | None = None,
    confidence: Decimal | float | int | None = None,
    quality: Decimal | float | int | None = None,
    supporting_factors: list[str] | None = None,
    conflicting_factors: list[str] | None = None,
    entry_context: dict[str, Any] | None = None,
    sl_tp_context: dict[str, Any] | None = None,
    valid_until: datetime | None = None,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
    duplicate: bool = False,
) -> SignalQualityScore:
    clock = now or datetime.now(UTC)
    regime = map_canonical_regime(regime_label, confidence=regime_confidence)

    def _score(v: object, default: Decimal = Decimal("0")) -> Decimal:
        if v is None:
            return default
        try:
            d = Decimal(str(v))
        except Exception:
            return default
        if d < 0:
            return Decimal("0")
        if d > 100:
            return Decimal("100")
        return d

    conf = _score(confidence, regime.confidence)
    qual = _score(quality)

    expiry = valid_until
    if expiry is None and ttl_seconds is not None and ttl_seconds > 0:
        expiry = clock + timedelta(seconds=int(ttl_seconds))

    stale = bool(expiry is not None and expiry <= clock) or duplicate
    risk = "elevated" if conflicting_factors else "standard"
    if regime.regime == CanonicalRegime.UNCERTAIN:
        risk = "uncertain_regime"
    if qual < 40:
        risk = "low_quality"

    actionable = (
        not stale
        and regime.regime != CanonicalRegime.UNCERTAIN
        and qual >= Decimal("50")
        and conf >= Decimal("50")
        and not duplicate
    )

    support = tuple(s for s in (supporting_factors or []) if s)
    conflict = tuple(c for c in (conflicting_factors or []) if c)
    parts = [
        f"quality={qual}",
        f"confidence={conf}",
        f"regime={regime.regime.value}",
    ]
    if support:
        parts.append("support=" + ",".join(support[:5]))
    if conflict:
        parts.append("conflict=" + ",".join(conflict[:5]))
    if stale:
        parts.append("stale_or_duplicate")

    return SignalQualityScore(
        symbol=(symbol or "").strip().upper(),
        direction=(direction or None),
        strategy_source=strategy_source,
        regime=regime.regime,
        confidence=conf,
        quality=qual,
        risk_assessment=risk,
        entry_context=entry_context,
        sl_tp_context=sl_tp_context,
        supporting_factors=support,
        conflicting_factors=conflict,
        valid_until=expiry,
        stale=stale,
        actionable=actionable,
        explanation="; ".join(parts),
        disclaimer=_DISCLAIMER,
        methodology={
            "actionable_rule": "quality>=50 and confidence>=50 and not stale "
            "and regime!=UNCERTAIN",
            "not_win_probability": True,
        },
    )
