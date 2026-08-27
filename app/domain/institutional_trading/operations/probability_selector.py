"""Authoritative Gold opportunity selector - Probability Center.

ONE formula. ONE threshold. Soft strategy evidence is weighted here.
Hard execution safety / market validity / risk remain fail-closed elsewhere.

This is an OPPORTUNITY SCORE (0..100), not a calibrated win probability.
Adaptive threshold decay is documented only and is DISABLED.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# Authoritative selector configuration - do not scatter these constants.
OPPORTUNITY_SCORE_THRESHOLD = 70
STRONG_CANDIDATE_THRESHOLD = 85
ADAPTIVE_THRESHOLD_ENABLED = False
ADAPTIVE_THRESHOLD_DESIGN = (
    "Future only: normal=70, strong=85, adaptive lowering disabled. "
    "Do not decay the threshold because the desk was idle."
)

SCORE_BAND_SETUP_NOT_READY = "SETUP_NOT_READY"
SCORE_BAND_CANDIDATE = "PROBABILITY_CANDIDATE"
SCORE_BAND_STRONG = "STRONG_CANDIDATE"

# Weights sum to 100. Present-only components are renormalized.
OPPORTUNITY_WEIGHTS: dict[str, int] = {
    "structure": 14,
    "momentum": 12,
    "consensus": 14,
    "regime_fit": 10,
    "price_action": 10,
    "liquidity": 10,
    "volatility": 8,
    "execution_quality": 10,
    "mtf_alignment": 6,
    "rr_quality": 6,
}

assert sum(OPPORTUNITY_WEIGHTS.values()) == 100

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
_RANGE_REGIMES = frozenset({"range", "ranging", "mean_reversion", "compression"})
_CHOP_REGIMES = frozenset({"chop", "choppy", "noise", "undefined"})


def _clamp_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, n))


def _smc_presence_score(raw: Any, *, absent_max: int = 30) -> int:
    """Map scoring sentinels (20/25 = absent) to 0; keep real 70–85 presence."""
    n = _clamp_int(raw, 0)
    if n is None or n <= absent_max:
        return 0
    return n


def _rr_quality(rr: Any) -> int | None:
    if rr is None or rr == "":
        return None
    try:
        value = float(rr)
    except (TypeError, ValueError):
        return None
    # Map RR 1.0-2.5 to ~40-100. Below 1.0 still contributes (does not AND-kill).
    mapped = round(40.0 + (value - 1.0) * 40.0)
    return max(0, min(100, mapped))


def _regime_fit(regime: Any) -> int | None:
    raw = str(regime or "").strip().lower()
    if not raw:
        return None
    if raw in _TREND_REGIMES or "trend" in raw or "breakout" in raw:
        if "weak" in raw:
            return 70
        return 80
    if raw in _RANGE_REGIMES:
        return 58
    if raw in _CHOP_REGIMES:
        return 35
    return 50


def _vol_component(raw: Any, decision: Mapping[str, Any] | None) -> int | None:
    if isinstance(decision, Mapping) and decision:
        if decision.get("passed") is True:
            return max(_clamp_int(raw, 70) or 70, 74)
        atr = decision.get("atr_pct")
        try:
            atr_f = float(atr) if atr is not None else None
        except (TypeError, ValueError):
            atr_f = None
        try:
            hard = float(decision.get("hard_min_pct") or 0)
        except (TypeError, ValueError):
            hard = 0.0
        if atr_f is None:
            return 0
        if hard > 0 and atr_f < hard:
            return 0
        # Compressed but above hard min - evidence, not a hard kill.
        return _clamp_int(raw, 40) or 40
    return _clamp_int(raw)


def score_band_for(score: int, *, threshold: int = OPPORTUNITY_SCORE_THRESHOLD) -> str:
    if score >= STRONG_CANDIDATE_THRESHOLD:
        return SCORE_BAND_STRONG
    if score >= threshold:
        return SCORE_BAND_CANDIDATE
    return SCORE_BAND_SETUP_NOT_READY


def weighted_opportunity_score(
    components: Mapping[str, int | None],
    *,
    weights: Mapping[str, int] | None = None,
) -> tuple[int, dict[str, int]]:
    """Deterministic present-only weighted aggregate, 0..100."""
    table = dict(weights or OPPORTUNITY_WEIGHTS)
    acc = 0.0
    total_w = 0
    breakdown: dict[str, int] = {}
    for name, weight in table.items():
        raw = components.get(name)
        if raw is None:
            continue
        clamped = max(0, min(100, int(raw)))
        breakdown[name] = clamped
        acc += clamped * int(weight)
        total_w += int(weight)
    if total_w <= 0:
        return 0, breakdown
    return max(0, min(100, round(acc / total_w))), breakdown


@dataclass(frozen=True, slots=True)
class OpportunityVerdict:
    opportunity_score: int
    threshold: int
    strong_threshold: int
    score_band: str
    score_breakdown: dict[str, int]
    weights_used: dict[str, int]
    direction: str
    direction_ok: bool
    eligible: bool
    blocking_stage: str | None
    fault_code: str | None
    fault_reason: str | None
    next_action: str
    adaptive_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_score": self.opportunity_score,
            "opportunity_threshold": self.threshold,
            "strong_threshold": self.strong_threshold,
            "score_band": self.score_band,
            "score_breakdown": dict(self.score_breakdown),
            "weights": dict(self.weights_used),
            "direction": self.direction,
            "direction_ok": self.direction_ok,
            "eligible": self.eligible,
            "blocking_stage": self.blocking_stage,
            "fault_code": self.fault_code,
            "fault_reason": self.fault_reason,
            "next_action": self.next_action,
            "adaptive_threshold_enabled": self.adaptive_enabled,
            "win_probability": False,
            "terminology": "OPPORTUNITY SCORE",
        }


def evaluate_opportunity(
    *,
    direction: str | None,
    structure: int | None = None,
    momentum: int | None = None,
    quality: int | None = None,
    confidence: int | None = None,
    regime: str | None = None,
    price_action: int | None = None,
    liquidity: int | None = None,
    volatility: int | None = None,
    execution_quality: int | None = None,
    mtf_alignment: int | None = None,
    risk_reward: Any = None,
    threshold: int = OPPORTUNITY_SCORE_THRESHOLD,
) -> OpportunityVerdict:
    """Build the authoritative opportunity score from existing strategy evidence."""
    consensus: int | None
    if quality is None and confidence is None:
        consensus = None
    elif quality is None:
        consensus = _clamp_int(confidence)
    elif confidence is None:
        consensus = _clamp_int(quality)
    else:
        consensus = _clamp_int((float(quality) + float(confidence)) / 2.0)

    components: dict[str, int | None] = {
        "structure": _clamp_int(structure),
        "momentum": _clamp_int(momentum),
        "consensus": consensus,
        "regime_fit": _regime_fit(regime),
        "price_action": _clamp_int(price_action),
        "liquidity": _clamp_int(liquidity),
        "volatility": _clamp_int(volatility),
        "execution_quality": _clamp_int(execution_quality),
        "mtf_alignment": _clamp_int(mtf_alignment),
        "rr_quality": _rr_quality(risk_reward),
    }
    score, breakdown = weighted_opportunity_score(components)
    used = {k: OPPORTUNITY_WEIGHTS[k] for k in breakdown}
    side = str(direction or "NONE").strip().upper() or "NONE"
    direction_ok = side in {"BUY", "SELL"}
    band = score_band_for(score, threshold=threshold)

    blocking_stage: str | None = None
    fault_code: str | None = None
    fault_reason: str | None = None
    next_action = "WAIT"
    eligible = False

    if score < threshold:
        blocking_stage = "PROBABILITY"
        fault_code = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
        fault_reason = (
            f"opportunity_score {score} < threshold {threshold} - WAIT"
        )
        next_action = "WAIT"
    elif not direction_ok:
        blocking_stage = "DECISION"
        fault_code = "DIRECTION_NONE"
        fault_reason = (
            "direction MUST be BUY or SELL - opportunity score cannot create a trade"
        )
        next_action = "WAIT"
    else:
        eligible = True
        next_action = "RISK_ASSESSMENT"

    return OpportunityVerdict(
        opportunity_score=score,
        threshold=int(threshold),
        strong_threshold=STRONG_CANDIDATE_THRESHOLD,
        score_band=band,
        score_breakdown=breakdown,
        weights_used=used,
        direction=side,
        direction_ok=direction_ok,
        eligible=eligible,
        blocking_stage=blocking_stage,
        fault_code=fault_code,
        fault_reason=fault_reason,
        next_action=next_action,
        adaptive_enabled=ADAPTIVE_THRESHOLD_ENABLED,
    )


def evaluate_from_score_dict(score: Mapping[str, Any]) -> OpportunityVerdict:
    """Map an existing AI scalping score artefact onto the selector."""
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    vol = (
        score.get("volatility_decision")
        if isinstance(score.get("volatility_decision"), dict)
        else {}
    )
    quality = _clamp_int(score.get("trade_quality") or score.get("quality"))
    confidence = _clamp_int(score.get("ai_confidence") or score.get("confidence"))
    structure = _clamp_int(
        score.get("structure_score") or factors.get("structure_score")
    )
    bos_q = _smc_presence_score(factors.get("bos"))
    choch_q = _smc_presence_score(factors.get("choch"))
    fvg_q = _smc_presence_score(factors.get("fvg"))
    ob_q = _smc_presence_score(factors.get("order_block"))
    smc = max(bos_q, choch_q, fvg_q, ob_q)
    if structure is None:
        if smc or factors.get("bos") is not None or factors.get("choch") is not None:
            structure = smc
    elif smc:
        # Do not ignore live FVG/OB/BOS presence when structure_score is range/alignment.
        structure = max(structure, smc)
    pa = _clamp_int(
        score.get("pa_confluence")
        or factors.get("pa_confluence")
        or factors.get("rsi")
    )
    liquidity = _clamp_int(score.get("liquidity") or factors.get("liquidity_sweep"))
    if fvg_q or ob_q:
        liquidity = max(liquidity or 0, fvg_q, ob_q)
    return evaluate_opportunity(
        direction=str(score.get("direction") or "NONE"),
        structure=structure,
        momentum=_clamp_int(
            score.get("momentum")
            or factors.get("momentum")
            or factors.get("trend_strength")
        ),
        quality=quality,
        confidence=confidence,
        regime=str(score.get("market_regime") or score.get("regime") or "") or None,
        price_action=pa,
        liquidity=liquidity,
        volatility=_vol_component(
            factors.get("volatility") or factors.get("atr_expansion"),
            vol if isinstance(vol, dict) else None,
        ),
        execution_quality=_clamp_int(
            score.get("spread_score") or factors.get("spread")
        ),
        mtf_alignment=_clamp_int(
            score.get("mtf_alignment") or factors.get("mtf") or factors.get("h1_bias")
        ),
        risk_reward=score.get("expected_rr") or score.get("risk_reward"),
    )


def evaluate_from_facts(facts: Any) -> OpportunityVerdict:
    """Gold execution contract path - reuse last selector score when present."""
    provided = getattr(facts, "opportunity_score", None)
    direction = str(getattr(facts, "direction", None) or "NONE")
    if provided is not None:
        score = _clamp_int(provided, 0) or 0
        breakdown = dict(getattr(facts, "score_breakdown", None) or {})
        threshold = int(
            getattr(facts, "opportunity_threshold", None) or OPPORTUNITY_SCORE_THRESHOLD
        )
        side = direction.strip().upper() or "NONE"
        direction_ok = side in {"BUY", "SELL"}
        band = score_band_for(score, threshold=threshold)
        eligible = score >= threshold and direction_ok
        blocking = None
        code = None
        reason = None
        nxt = "RISK_ASSESSMENT" if eligible else "WAIT"
        if score < threshold:
            blocking = "PROBABILITY"
            code = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
            reason = f"opportunity_score {score} < threshold {threshold} - WAIT"
        elif not direction_ok:
            blocking = "DECISION"
            code = "DIRECTION_NONE"
            reason = (
                "direction MUST be BUY or SELL - "
                "opportunity score cannot create a trade"
            )
        return OpportunityVerdict(
            opportunity_score=score,
            threshold=threshold,
            strong_threshold=STRONG_CANDIDATE_THRESHOLD,
            score_band=band,
            score_breakdown=breakdown,
            weights_used=dict(OPPORTUNITY_WEIGHTS),
            direction=side,
            direction_ok=direction_ok,
            eligible=eligible,
            blocking_stage=blocking,
            fault_code=code,
            fault_reason=reason,
            next_action=nxt,
            adaptive_enabled=ADAPTIVE_THRESHOLD_ENABLED,
        )

    vol_ok = bool(getattr(facts, "volatility_ok", True))
    spread = getattr(facts, "spread", None)
    exec_q: int | None = None
    if spread is not None:
        try:
            spread_f = float(spread)
            # Tight gold spread (~0.20) -> high execution quality; 2.00 max -> 0.
            exec_q = max(0, min(100, round(100.0 * (1.0 - (spread_f / 2.0)))))
        except (TypeError, ValueError):
            exec_q = None
    return evaluate_opportunity(
        direction=direction,
        structure=_clamp_int(getattr(facts, "structure_score", None)),
        momentum=_clamp_int(getattr(facts, "momentum_score", None)),
        quality=_clamp_int(getattr(facts, "quality", None)),
        confidence=_clamp_int(getattr(facts, "confidence", None)),
        regime=getattr(facts, "market_regime", None),
        price_action=_clamp_int(getattr(facts, "pa_confluence", None)),
        liquidity=_clamp_int(getattr(facts, "liquidity_score", None)),
        volatility=80 if vol_ok else 20,
        execution_quality=exec_q,
        mtf_alignment=_clamp_int(getattr(facts, "mtf_alignment", None)),
        risk_reward=getattr(facts, "risk_reward", None),
    )


def rr_quality_from_decimal(rr: Decimal | None) -> int | None:
    return _rr_quality(rr)
