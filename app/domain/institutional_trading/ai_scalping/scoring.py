"""AI Scalping score — structure + momentum + session + spread + history."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    AiScalpingConfig,
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.regime import (
    RegimeAssessment,
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_structure.enums import StructureBreakKind, TrendDirection


@dataclass(frozen=True, slots=True)
class AiScalpingScore:
    confidence: int
    trade_quality: int
    confluence: int
    expected_rr: Decimal | None
    expected_hold_time: str
    market_regime: str
    momentum: int
    liquidity: int
    spread_score: int
    atr_pct: Decimal | None
    direction: str
    factors: dict[str, int]
    thresholds: dict[str, object]
    reasons: tuple[str, ...]
    reject: bool
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_confidence": self.confidence,
            "trade_quality": self.trade_quality,
            "confluence": self.confluence,
            "expected_rr": str(self.expected_rr) if self.expected_rr is not None else None,
            "expected_hold_time": self.expected_hold_time,
            "market_regime": self.market_regime,
            "momentum": self.momentum,
            "liquidity": self.liquidity,
            "spread_score": self.spread_score,
            "atr_pct": str(self.atr_pct) if self.atr_pct is not None else None,
            "direction": self.direction,
            "factors": dict(self.factors),
            "thresholds": dict(self.thresholds),
            "reasons": list(self.reasons),
            "reject": self.reject,
            "reject_reason": self.reject_reason,
        }


def _hold_time_for_regime(regime: str) -> str:
    mapping = {
        "breakout": "5–20m",
        "trending": "15–45m",
        "reversal": "10–30m",
        "range": "5–15m",
        "accumulation": "20–60m",
        "distribution": "20–60m",
    }
    return mapping.get(regime, "10–30m")


def score_scalping_setup(
    snapshot: MarketAnalysisSnapshot,
    *,
    atr: Decimal | None,
    mid: Decimal | None,
    historical_similarity: int | None = None,
    config: AiScalpingConfig | None = None,
) -> AiScalpingScore:
    """Compute AI Confidence / Quality / Confluence for scalping mode."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    reasons: list[str] = []
    factors: dict[str, int] = {}

    trend = snapshot.trend
    quality = snapshot.trade_quality
    structure = snapshot.primary_structure

    # Direction from H1 (macro after remap) — never require H4
    direction = TradeDirection.NONE
    if trend.macro_bias in {TrendDirection.UP, TrendDirection.DOWN}:
        if trend.macro_bias == trend.primary or trend.alignment_score >= 55:
            direction = (
                TradeDirection.BUY
                if trend.macro_bias is TrendDirection.UP
                else TradeDirection.SELL
            )
            reasons.append(
                f"Direction filter {cfg.direction_tf.value}={trend.macro_bias.value} "
                f"(structure {cfg.structure_tf.value}={trend.primary.value})"
            )
            factors["mtf"] = max(trend.alignment_score, 55)
        else:
            factors["mtf"] = max(0, trend.alignment_score // 2)
            reasons.append(trend.why or "MTF weak for scalping")
    else:
        factors["mtf"] = 0
        reasons.append("No clear H1 direction")

    bos = len(structure.breaks_of_structure) if structure else 0
    choch = len(structure.changes_of_character) if structure else 0
    factors["bos"] = 90 if bos else 20
    factors["choch"] = 85 if choch else 20
    if bos or choch:
        reasons.append(f"Structure bos={bos} choch={choch}")

    liq = snapshot.liquidity
    sweeps = len(liq.sweeps) if liq else 0
    factors["liquidity_sweep"] = 88 if sweeps else 25
    if sweeps:
        reasons.append(f"Liquidity sweeps={sweeps}")

    ob = snapshot.order_blocks
    active_ob = 0
    if ob:
        active_ob = sum(
            1
            for b in ob.order_blocks
            if str(getattr(getattr(b, "state", None), "value", b.state)).lower()
            in {"active", "validated"}
        )
    factors["order_block"] = 85 if active_ob else 20

    fvg = snapshot.fair_value_gaps
    open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
    factors["fvg"] = 80 if open_fvg else 25

    resolved: ResolvedThresholds = resolve_adaptive_thresholds(atr, mid, config=cfg)
    factors["atr_expansion"] = (
        85 if resolved.band == "high" else (70 if resolved.band == "normal" else 55)
    )

    # Volume / momentum proxies from quality components when present
    q_components = getattr(quality, "components", None) or {}
    vol_score = int(q_components.get("volume", q_components.get("vol", 60)) or 60)
    mom_score = int(
        q_components.get("momentum", q_components.get("trend_strength", 60)) or 60
    )
    factors["volume"] = max(0, min(100, vol_score))
    factors["momentum"] = max(0, min(100, mom_score))
    factors["trend_strength"] = int(trend.alignment_score)
    factors["volatility"] = factors["atr_expansion"]

    session = assess_session(
        str(getattr(snapshot.session.session, "value", snapshot.session.session)),
        config=cfg,
    )
    factors["session"] = 100 if session.aggressive else max(20, 100 - session.confidence_penalty * 5)
    reasons.append(session.reason)

    spread_a = assess_spread(snapshot.spread, config=cfg)
    factors["spread"] = spread_a.score
    reasons.append(spread_a.reason)

    hist = int(historical_similarity) if historical_similarity is not None else 55
    factors["historical_similar"] = max(0, min(100, hist))

    weights = {
        "mtf": 18,
        "bos": 8,
        "choch": 7,
        "liquidity_sweep": 10,
        "order_block": 10,
        "fvg": 8,
        "atr_expansion": 6,
        "volume": 5,
        "momentum": 7,
        "trend_strength": 6,
        "volatility": 3,
        "session": 5,
        "spread": 4,
        "historical_similar": 3,
    }
    weighted = sum(factors.get(k, 0) * w for k, w in weights.items())
    total_w = sum(weights.values())
    confidence = round(weighted / total_w) if total_w else 0
    confidence -= session.confidence_penalty
    confidence -= spread_a.confidence_penalty
    confidence = max(0, min(100, confidence))

    trade_quality = int(quality.total)
    confluence = confidence  # scalping confluence aligns with AI confidence

    regime: RegimeAssessment = classify_scalping_regime(
        alignment_score=int(trend.alignment_score),
        atr_pct=resolved.atr_pct,
        bos=bos,
        choch=choch,
        sweep_count=sweeps,
        range_like=trend.alignment_score < 55,
        volume_expanding=factors["volume"] >= 70,
    )
    reasons.extend(regime.reasons)

    expected_rr = Decimal("1.5")
    if regime.regime == "breakout":
        expected_rr = Decimal("2.0")
    elif regime.regime == "range":
        expected_rr = Decimal("1.2")

    reject = False
    reject_reason = None
    if spread_a.reject:
        reject = True
        reject_reason = spread_a.reason
        direction = TradeDirection.NONE
    elif confidence < resolved.confidence or trade_quality < resolved.quality:
        reject = True
        reject_reason = (
            f"Below adaptive gates Q≥{resolved.quality} C≥{resolved.confidence} "
            f"(got Q{trade_quality}/C{confidence}, band={resolved.band})"
        )
        direction = TradeDirection.NONE
    elif direction is TradeDirection.NONE:
        reject = True
        reject_reason = "No scalable direction from H1 filter"

    return AiScalpingScore(
        confidence=confidence,
        trade_quality=trade_quality,
        confluence=confluence,
        expected_rr=expected_rr,
        expected_hold_time=_hold_time_for_regime(regime.regime),
        market_regime=regime.regime,
        momentum=factors["momentum"],
        liquidity=factors["liquidity_sweep"],
        spread_score=spread_a.score,
        atr_pct=resolved.atr_pct,
        direction=direction.value,
        factors=factors,
        thresholds=resolved.to_dict(),
        reasons=tuple(reasons),
        reject=reject,
        reject_reason=reject_reason,
    )
