"""Global market intelligence alignment — soft confirmation layer.

Does not replace Opportunity Score / P>70 / Sniper / Risk / Safety.
Uses only legitimately available inputs. Missing feeds → SOURCE_UNAVAILABLE.
UNKNOWN is never treated as confirmation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

IMPACT_LEVELS = (
    "VERY_HIGH_IMPACT",
    "HIGH_IMPACT",
    "MEDIUM_IMPACT",
    "LOW_IMPACT",
    "NO_ACTIONABLE_IMPACT",
)

GLOBAL_REGIMES = (
    "RISK_ON",
    "RISK_OFF",
    "NEUTRAL",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "EVENT_RISK",
    "TRANSITION",
    "UNKNOWN",
)

ALIGNMENT_STATES = (
    "STRONGLY_ALIGNED",
    "ALIGNED",
    "NEUTRAL",
    "CONFLICTED",
    "HIGH_RISK",
    "UNKNOWN",
)

LAYER_STATES = ("CONFIRMATION", "CONTRADICTION", "UNKNOWN")


@dataclass(frozen=True, slots=True)
class IntelligenceItem:
    source: str
    timestamp: str
    symbol_relevance: str
    event_type: str
    direction_bias: str | None
    confidence: int
    freshness_seconds: int | None
    importance: str
    affected_assets: tuple[str, ...]
    confirmed: bool
    status: str  # available | SOURCE_UNAVAILABLE | stale

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "symbol_relevance": self.symbol_relevance,
            "event_type": self.event_type,
            "direction_bias": self.direction_bias,
            "confidence": self.confidence,
            "freshness_seconds": self.freshness_seconds,
            "importance": self.importance,
            "affected_assets": list(self.affected_assets),
            "confirmed": self.confirmed,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class LayerAssessment:
    name: str
    state: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class GlobalMarketIntelligence:
    """Independent of Opportunity Score — never overrides hard Safety/Risk."""

    global_regime: str
    intelligence_alignment: str
    layers: tuple[LayerAssessment, ...]
    sources: tuple[IntelligenceItem, ...]
    technical_score: int
    structure_score: int
    market_regime_score: int
    macro_alignment_score: int
    news_risk_score: int
    cross_asset_score: int
    execution_quality_score: int
    expected_reward_score: int
    wait_recommended: bool
    wait_code: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_regime": self.global_regime,
            "intelligence_alignment": self.intelligence_alignment,
            "layers": [layer.to_dict() for layer in self.layers],
            "sources": [item.to_dict() for item in self.sources],
            "technical_score": self.technical_score,
            "structure_score": self.structure_score,
            "market_regime_score": self.market_regime_score,
            "macro_alignment_score": self.macro_alignment_score,
            "news_risk_score": self.news_risk_score,
            "cross_asset_score": self.cross_asset_score,
            "execution_quality_score": self.execution_quality_score,
            "expected_reward_score": self.expected_reward_score,
            "wait_recommended": self.wait_recommended,
            "wait_code": self.wait_code,
            "reason": self.reason,
            "opportunity_score_unchanged": True,
            "never_overrides_safety_risk": True,
        }


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def _unavailable(source: str, event_type: str) -> IntelligenceItem:
    return IntelligenceItem(
        source=source,
        timestamp=datetime.now(UTC).isoformat(),
        symbol_relevance="*",
        event_type=event_type,
        direction_bias=None,
        confidence=0,
        freshness_seconds=None,
        importance="NO_ACTIONABLE_IMPACT",
        affected_assets=(),
        confirmed=False,
        status="SOURCE_UNAVAILABLE",
    )


def _configured_feed_statuses() -> tuple[IntelligenceItem, ...]:
    """Inspect settings for news/calendar providers — never fabricate payloads."""
    items: list[IntelligenceItem] = []
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return (
            _unavailable("settings", "provider_registry"),
            _unavailable("economic_calendar", "calendar"),
            _unavailable("finnhub", "news_calendar_sentiment"),
            _unavailable("trading_economics", "calendar"),
        )

    pairs = (
        ("economic_calendar_feed_url", "economic_calendar", "calendar"),
        ("news_intelligence_feed_url", "news_intelligence", "news"),
        ("finnhub_api_key", "finnhub", "news_calendar_sentiment"),
        ("trading_economics_api_key", "trading_economics", "calendar"),
        ("alphavantage_api_key", "alphavantage", "sentiment_quotes"),
        ("polygon_api_key", "polygon", "news_quotes"),
        ("twelvedata_api_key", "twelvedata", "quotes"),
    )
    for attr, source, event_type in pairs:
        raw = str(getattr(settings, attr, "") or "").strip()
        if raw:
            items.append(
                IntelligenceItem(
                    source=source,
                    timestamp=datetime.now(UTC).isoformat(),
                    symbol_relevance="*",
                    event_type=event_type,
                    direction_bias=None,
                    confidence=40,
                    freshness_seconds=None,
                    importance="MEDIUM_IMPACT",
                    affected_assets=(),
                    confirmed=False,
                    status="available",
                )
            )
        else:
            items.append(_unavailable(source, event_type))
    return tuple(items)


def _layer(
    name: str,
    *,
    confirmation: bool | None,
    score: int,
    reason: str,
) -> LayerAssessment:
    if confirmation is True:
        state = "CONFIRMATION"
    elif confirmation is False:
        state = "CONTRADICTION"
    else:
        state = "UNKNOWN"
    return LayerAssessment(name=name, state=state, score=_clamp(score), reason=reason)


def assess_global_market_intelligence(
    *,
    direction: str | None,
    structure_score: int = 0,
    momentum: int = 0,
    liquidity: int = 0,
    expected_rr: float | None = None,
    min_expected_rr: float = 1.0,
    market_regime: str | None = None,
    atr_band: str | None = None,
    news_blocked: bool = False,
    news_reason: str | None = None,
    mtf_alignment: int | None = None,
    execution_quality_ok: bool = True,
    portfolio_ok: bool = True,
    extras: Mapping[str, Any] | None = None,
) -> GlobalMarketIntelligence:
    """Build intelligence alignment from live artefacts + configured source status."""
    _ = extras
    sources = _configured_feed_statuses()
    side = str(direction or "").strip().upper()
    regime_raw = str(market_regime or "").strip().lower()
    band = str(atr_band or "").strip().lower()

    if news_blocked:
        global_regime = "EVENT_RISK"
    elif band in {"high", "expansion"} or "expansion" in regime_raw:
        global_regime = "HIGH_VOLATILITY"
    elif band in {"low", "compression"} or "compression" in regime_raw:
        global_regime = "LOW_VOLATILITY"
    elif "breakout" in regime_raw or "transition" in regime_raw:
        global_regime = "TRANSITION"
    elif side in {"BUY", "SELL"} and (mtf_alignment or 0) >= 70:
        # Price-structure lean only — not fabricated macro risk-on/off.
        global_regime = "NEUTRAL"
    else:
        global_regime = "UNKNOWN"

    if structure_score or momentum:
        technical = _clamp(int((structure_score + momentum) / 2))
    else:
        technical = 0
    structure = _clamp(structure_score)
    regime_score = (
        30
        if global_regime == "EVENT_RISK"
        else (
            45
            if global_regime == "LOW_VOLATILITY"
            else (55 if global_regime == "HIGH_VOLATILITY" else 60)
        )
    )
    # Macro feeds are mostly SOURCE_UNAVAILABLE in this environment — do not invent.
    available_macro = [s for s in sources if s.status == "available"]
    if news_blocked:
        macro = 15
        news_risk = 10
        macro_state: bool | None = False
        macro_reason = news_reason or "High-impact news blackout"
    elif not available_macro:
        macro = 50
        news_risk = 50
        macro_state = None
        macro_reason = "SOURCE_UNAVAILABLE - no macro/news feed configured"
    else:
        macro = 55
        news_risk = 60
        macro_state = None
        macro_reason = (
            f"{len(available_macro)} provider credential(s) present; "
            "no confirmed directional macro bias without live event payload"
        )

    # MTF alignment is a confirmation scalar, not an opposing-bias signal.
    # Missing/zero/weak alignment → UNKNOWN (never confirmation, never hard conflict).
    # Inventing "conflicts with BUY/SELL" from low alignment was a production defect
    # that emitted WAIT_INTELLIGENCE_CONFLICT for otherwise valid P>70 setups.
    cross = 50
    cross_state: bool | None = None
    if mtf_alignment is None or int(mtf_alignment) <= 0:
        cross_reason = "MTF alignment unavailable/unknown — not a contradiction"
    elif mtf_alignment >= 70 and side in {"BUY", "SELL"}:
        cross = 75
        cross_state = True
        cross_reason = f"MTF alignment {mtf_alignment} supports {side}"
    elif mtf_alignment < 40 and side in {"BUY", "SELL"}:
        cross = 40
        cross_state = None
        cross_reason = (
            f"MTF alignment {mtf_alignment} weak/UNKNOWN "
            f"(lack of confirmation ≠ directional conflict with {side})"
        )
    else:
        cross_reason = f"MTF alignment {mtf_alignment} neutral/unknown"

    exec_score = 75 if execution_quality_ok else 25
    reward = 50
    if expected_rr is not None and expected_rr > 0:
        if expected_rr >= max(float(min_expected_rr), 1.5):
            reward = 85
        elif expected_rr > 1.0:
            reward = 65
        else:
            reward = 25

    layers = (
        _layer(
            "structure",
            # Weak structure is lack of confirmation — Sniper already gates quality.
            # Do not relabel weak scores as hard CONTRADICTION.
            confirmation=(True if structure >= 70 else None),
            score=structure,
            reason=f"structure_score={structure}",
        ),
        _layer(
            "liquidity",
            confirmation=(True if liquidity >= 70 else None),
            score=_clamp(liquidity),
            reason=f"liquidity={liquidity}",
        ),
        _layer(
            "momentum",
            confirmation=(True if momentum >= 70 else None),
            score=_clamp(momentum),
            reason=f"momentum={momentum}",
        ),
        _layer(
            "volatility",
            confirmation=None if global_regime == "UNKNOWN" else True,
            score=regime_score,
            reason=f"regime={global_regime} atr_band={band or 'n/a'}",
        ),
        _layer(
            "risk_reward",
            confirmation=(
                True
                if expected_rr is not None and expected_rr > 1.0
                else (False if expected_rr is not None else None)
            ),
            score=reward,
            reason=f"expected_rr={expected_rr}",
        ),
        _layer(
            "market_regime",
            confirmation=False if global_regime == "EVENT_RISK" else None,
            score=regime_score,
            reason=f"global_regime={global_regime}",
        ),
        _layer(
            "macro_news",
            confirmation=macro_state,
            score=macro,
            reason=macro_reason,
        ),
        _layer(
            "cross_asset",
            confirmation=cross_state,
            score=cross,
            reason=cross_reason,
        ),
        _layer(
            "execution_quality",
            confirmation=bool(execution_quality_ok),
            score=exec_score,
            reason=(
                "execution_quality_ok"
                if execution_quality_ok
                else "execution_degraded"
            ),
        ),
        _layer(
            "portfolio_exposure",
            confirmation=bool(portfolio_ok),
            score=70 if portfolio_ok else 20,
            reason="portfolio_ok" if portfolio_ok else "portfolio_blocked",
        ),
    )

    contradictions = [layer for layer in layers if layer.state == "CONTRADICTION"]
    confirmations = [layer for layer in layers if layer.state == "CONFIRMATION"]

    wait_code: str | None = None
    wait_recommended = False
    # Hard WAIT only on affirmative opposing/degraded evidence — never on UNKNOWN.
    hard_names = {
        "execution_quality",
        "portfolio_exposure",
        "market_regime",
    }
    if news_blocked or global_regime == "EVENT_RISK":
        alignment = "HIGH_RISK"
        wait_recommended = True
        wait_code = "WAIT_EVENT_RISK"
        reason = macro_reason
    elif any(
        layer.name in hard_names and layer.state == "CONTRADICTION"
        for layer in contradictions
    ):
        alignment = "CONFLICTED"
        hard = [layer for layer in contradictions if layer.name in hard_names]
        wait_recommended = True
        wait_code = "WAIT_INTELLIGENCE_CONFLICT"
        reason = "; ".join(layer.reason for layer in hard) or "Intelligence conflict"
    elif len(confirmations) >= 5 and not contradictions:
        alignment = "STRONGLY_ALIGNED"
        reason = "Multiple independent confirmations; no contradictions"
    elif len(confirmations) >= 3:
        alignment = "ALIGNED"
        reason = "Partial multi-layer confirmation"
    elif not confirmations and not contradictions:
        alignment = "UNKNOWN"
        reason = "Insufficient confirmed intelligence — UNKNOWN is not confirmation"
    else:
        alignment = "NEUTRAL"
        reason = "Mixed or weak intelligence signal"

    return GlobalMarketIntelligence(
        global_regime=global_regime,
        intelligence_alignment=alignment,
        layers=layers,
        sources=sources,
        technical_score=technical,
        structure_score=structure,
        market_regime_score=regime_score,
        macro_alignment_score=macro,
        news_risk_score=news_risk,
        cross_asset_score=cross,
        execution_quality_score=exec_score,
        expected_reward_score=reward,
        wait_recommended=wait_recommended,
        wait_code=wait_code,
        reason=reason,
    )
