"""AI Scalping score v6 - institutional quality, balanced BUY/SELL, 1-10m hold."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.pa_confluence import (
    evaluate_pa_confluence,
)
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.regime import (
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot

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
    buy_score: int = 0
    sell_score: int = 0
    structure_score: int = 0
    entry: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    quality_checks: dict[str, bool] | None = None
    reject_reasons: tuple[str, ...] = ()
    indicators: dict[str, object] | None = None
    entry_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_confidence": self.confidence,
            "trade_quality": self.trade_quality,
            "confluence": self.confluence,
            "expected_rr": (
                str(self.expected_rr) if self.expected_rr is not None else None
            ),
            "expected_hold_time": self.expected_hold_time,
            "market_regime": self.market_regime,
            "momentum": self.momentum,
            "liquidity": self.liquidity,
            "spread_score": self.spread_score,
            "atr_pct": str(self.atr_pct) if self.atr_pct is not None else None,
            "direction": self.direction,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "structure_score": self.structure_score,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "factors": dict(self.factors),
            "thresholds": dict(self.thresholds),
            "reasons": list(self.reasons),
            "reject": self.reject,
            "reject_reason": self.reject_reason,
            "reject_reasons": list(self.reject_reasons),
            "quality_checks": dict(self.quality_checks or {}),
            "indicators": dict(self.indicators or {}),
            "entry_reason": self.entry_reason,
            "never_prefer_buy_only": True,
        }


def _hold_time(cfg: AiScalpingConfig, confidence: int, regime: str) -> str:
    lo = cfg.typical_hold_min_minutes
    hi = cfg.typical_hold_max_minutes
    if confidence >= cfg.high_confidence_for_extend and regime in {
        "trending",
        "breakout",
    }:
        hi = cfg.max_hold_minutes_if_confident
    return f"{lo}-{hi}m"


def score_scalping_setup(
    snapshot: MarketAnalysisSnapshot,
    *,
    atr: Decimal | None,
    mid: Decimal | None,
    historical_similarity: int | None = None,
    config: AiScalpingConfig | None = None,
    closes: Sequence[float] | None = None,
    opens: Sequence[float] | None = None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
) -> AiScalpingScore:
    """Compute AI Confidence / Quality for institutional scalping."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    reasons: list[str] = []
    factors: dict[str, int] = {}

    trend = snapshot.trend
    quality = snapshot.trade_quality
    structure = snapshot.primary_structure

    direction_dec = decide_scalping_direction(snapshot, config=cfg)
    reasons.extend(direction_dec.reasons)
    factors.update(direction_dec.factors)
    direction = direction_dec.direction

    bos = len(structure.breaks_of_structure) if structure else 0
    choch = len(structure.changes_of_character) if structure else 0
    if bos or choch:
        reasons.append(f"Structure bos={bos} choch={choch}")

    liq = snapshot.liquidity
    sweeps = len(liq.sweeps) if liq else 0
    liquidity_score = (
        88
        if sweeps
        else max(
            20,
            int((getattr(quality, "components", {}) or {}).get("liquidity", 40) or 40),
        )
    )
    factors["liquidity_sweep"] = liquidity_score
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
        85 if resolved.band == "high" else (70 if resolved.band == "normal" else 50)
    )

    q_components = getattr(quality, "components", None) or {}
    vol_score = int(q_components.get("volume", q_components.get("vol", 55)) or 55)
    mom_score = int(
        q_components.get("momentum", q_components.get("trend_strength", 55)) or 55
    )
    factors["volume"] = max(0, min(100, vol_score))
    factors["momentum"] = max(0, min(100, mom_score))
    factors["trend_strength"] = int(trend.alignment_score)
    factors["volatility"] = factors["atr_expansion"]
    factors["mtf"] = factors.get("h1_bias", 0) + factors.get("m15_structure", 0)

    session = assess_session(
        str(getattr(snapshot.session.session, "value", snapshot.session.session)),
        config=cfg,
    )
    factors["session"] = (
        100 if session.aggressive else max(15, 100 - session.confidence_penalty * 6)
    )
    reasons.append(session.reason)

    spread_a = assess_spread(snapshot.spread, config=cfg)
    factors["spread"] = spread_a.score
    reasons.append(spread_a.reason)

    hist = int(historical_similarity) if historical_similarity is not None else 50
    factors["historical_similar"] = max(0, min(100, hist))

    pa = evaluate_pa_confluence(
        snapshot,
        direction=direction,
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        config=cfg,
    )
    factors["ema"] = pa.ema_score
    factors["rsi"] = pa.rsi_score
    factors["candle_pa"] = pa.candle_score
    factors["pa_confluence"] = pa.score
    reasons.extend(pa.reasons)

    weights = {
        "mtf": 14,
        "bos": 7,
        "choch": 7,
        "liquidity_sweep": 10,
        "order_block": 8,
        "fvg": 7,
        "atr_expansion": 5,
        "volume": 4,
        "momentum": 8,
        "trend_strength": 4,
        "volatility": 3,
        "session": 5,
        "spread": 4,
        "historical_similar": 2,
        "ema": 5,
        "rsi": 4,
        "candle_pa": 3,
    }
    weighted = sum(factors.get(k, 0) * w for k, w in weights.items())
    total_w = sum(weights.values())
    confidence = round(weighted / total_w) if total_w else 0
    confidence -= session.confidence_penalty
    confidence -= spread_a.confidence_penalty
    confidence = max(0, min(100, confidence))

    trade_quality = int(quality.total)
    confluence = confidence

    regime = classify_scalping_regime(
        alignment_score=int(trend.alignment_score),
        atr_pct=resolved.atr_pct,
        bos=bos,
        choch=choch,
        sweep_count=sweeps,
        range_like=trend.alignment_score < 55,
        volume_expanding=factors["volume"] >= 70,
    )
    reasons.extend(regime.reasons)

    targets = compute_structure_targets(
        snapshot,
        direction=direction,
        entry=mid,
        atr=atr,
        config=cfg,
    )
    expected_rr = targets.expected_rr or Decimal("1.4")
    if targets.reason:
        reasons.append(targets.reason)

    gates = evaluate_quality_gates(
        direction=direction_dec,
        momentum=factors["momentum"],
        liquidity=liquidity_score,
        structure_score=direction_dec.structure_score,
        session=session,
        spread=spread_a,
        thresholds=resolved,
        confidence=confidence,
        trade_quality=trade_quality,
        expected_rr=expected_rr,
        atr_pct=resolved.atr_pct,
        config=cfg,
        pa_confluence=pa,
    )

    reject = not gates.passed
    reject_reason = "; ".join(gates.rejects) if gates.rejects else None
    if reject:
        direction = TradeDirection.NONE
        for r in gates.rejects:
            reasons.append(f"REJECT: {r}")
        entry_reason = reject_reason
    else:
        entry_reason = (
            f"TAKE {direction_dec.direction.value}: "
            f"PA={pa.score} conf={confidence} "
            f"EMA/RSI/SMC confluence satisfied"
        )
        reasons.append(
            f"TAKE {direction_dec.direction.value}: all institutional quality gates passed"  # noqa: E501
        )

    hold = _hold_time(cfg, confidence, regime.regime)

    return AiScalpingScore(
        confidence=confidence,
        trade_quality=trade_quality,
        confluence=confluence,
        expected_rr=expected_rr,
        expected_hold_time=hold,
        market_regime=regime.regime,
        momentum=factors["momentum"],
        liquidity=liquidity_score,
        spread_score=spread_a.score,
        atr_pct=resolved.atr_pct,
        direction=direction.value if not reject else TradeDirection.NONE.value,
        factors=factors,
        thresholds=resolved.to_dict(),
        reasons=tuple(reasons),
        reject=reject,
        reject_reason=reject_reason,
        buy_score=direction_dec.buy_score,
        sell_score=direction_dec.sell_score,
        structure_score=direction_dec.structure_score,
        entry=str(targets.entry) if targets.entry is not None else None,
        stop_loss=str(targets.stop_loss) if targets.stop_loss is not None else None,
        take_profit=(
            str(targets.take_profit) if targets.take_profit is not None else None
        ),
        quality_checks=gates.checks,
        reject_reasons=gates.rejects,
        indicators=pa.indicators,
        entry_reason=entry_reason,
    )
