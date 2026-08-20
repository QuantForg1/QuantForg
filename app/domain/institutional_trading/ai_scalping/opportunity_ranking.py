"""Institutional Opportunity Ranking Engine — aggregate existing AI factors only.

Produces Opportunity Score 0–100 from live scalping score artefacts.
Does not invent metrics, lower floors, or force trades.
"""

from __future__ import annotations

from typing import Any


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, n))


def compute_opportunity_components(score: dict[str, Any]) -> dict[str, int]:
    """Map existing AI score / factors into named institutional components."""
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    vol = (
        score.get("volatility_decision")
        if isinstance(score.get("volatility_decision"), dict)
        else {}
    )
    quality = _i(score.get("trade_quality") or score.get("quality"))
    confidence = _i(score.get("ai_confidence") or score.get("confidence"))
    mtf = _i(score.get("mtf_alignment") or factors.get("mtf") or factors.get("h1_bias"))
    liquidity = _i(score.get("liquidity") or factors.get("liquidity_sweep"))
    volatility = _i(factors.get("volatility") or factors.get("atr_expansion") or 50)
    if vol:
        volatility = 85 if vol.get("passed") else max(10, volatility // 2)
    spread = _i(score.get("spread_score") or factors.get("spread") or 50)
    session = _i(factors.get("session") or 50)
    news_blocked = bool(score.get("news_blocked"))
    news = 20 if news_blocked else _i(factors.get("news") or 80)
    trend = _i(factors.get("trend_strength") or factors.get("momentum") or 50)
    structure = _i(factors.get("bos") or factors.get("choch") or 40)
    if factors.get("bos") and factors.get("choch"):
        structure = max(
            structure,
            (_i(factors.get("bos")) + _i(factors.get("choch"))) // 2,
        )
    order_block = _i(factors.get("order_block") or 40)
    fvg = _i(factors.get("fvg") or 40)
    rr_raw = score.get("expected_rr")
    try:
        rr = float(rr_raw) if rr_raw is not None else 0.0
    except Exception:
        rr = 0.0
    # Map RR 1.0–2.5 → ~40–100
    risk_reward = int(_clamp(40 + (rr - 1.0) * 40))
    # Execution probability 0–100 from existing AI estimate when present
    raw_prob = score.get("probability")
    prob = raw_prob if isinstance(raw_prob, dict) else {}
    p_success = score.get("estimated_probability")
    if p_success is None and prob:
        p_success = prob.get("probability_of_success")
    if p_success is not None:
        try:
            execution_probability = int(_clamp(float(p_success) * 100.0))
        except Exception:
            execution_probability = int(_clamp(0.5 * (quality + confidence)))
    else:
        execution_probability = int(_clamp(0.5 * (quality + confidence)))
    return {
        "ai_quality": max(0, min(100, quality)),
        "confidence": max(0, min(100, confidence)),
        "mtf_alignment": max(0, min(100, mtf)),
        "liquidity": max(0, min(100, liquidity)),
        "volatility": max(0, min(100, volatility)),
        "spread_quality": max(0, min(100, spread)),
        "session_quality": max(0, min(100, session)),
        "news_risk": max(0, min(100, news)),  # higher = safer (less news risk)
        "trend_strength": max(0, min(100, trend)),
        "structure_quality": max(0, min(100, structure)),
        "order_block_quality": max(0, min(100, order_block)),
        "fvg_quality": max(0, min(100, fvg)),
        "risk_reward": max(0, min(100, risk_reward)),
        "execution_probability": max(0, min(100, execution_probability)),
    }


def compute_opportunity_score(score: dict[str, Any]) -> dict[str, Any]:
    """Weighted Opportunity Score 0-100. Probability Center is the selector."""
    from app.domain.institutional_trading.operations.probability_selector import (
        OPPORTUNITY_WEIGHTS,
        evaluate_from_score_dict,
    )

    c = compute_opportunity_components(score)
    verdict = evaluate_from_score_dict(score)
    eligible = bool(verdict.eligible)
    if bool(score.get("reject")):
        reason = str(score.get("reject_reason") or "").lower()
        if "opportunity_score" not in reason:
            eligible = False
    return {
        "opportunity_score": verdict.opportunity_score,
        "components": c,
        "breakdown": dict(verdict.score_breakdown),
        "eligible": eligible and verdict.eligible,
        "score_band": verdict.score_band,
        "symbol": str(score.get("symbol") or "").upper(),
        "direction": verdict.direction,
        "reject": bool(score.get("reject")),
        "blocking_gate": score.get("reject_reason")
        or score.get("blocking_gate")
        or verdict.fault_code,
        "weights": dict(OPPORTUNITY_WEIGHTS),
        "fabricated": False,
        "source": "probability_center",
        "opportunity_threshold": verdict.threshold,
        "win_probability": False,
    }


def enrich_scores_with_opportunity(
    scored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach opportunity_score to each score row (immutable copy)."""
    out: list[dict[str, Any]] = []
    for row in scored:
        base = dict(row)
        opp = compute_opportunity_score(base)
        base["opportunity_score"] = opp["opportunity_score"]
        base["opportunity_components"] = opp["components"]
        base["opportunity_eligible"] = opp["eligible"]
        base["score_band"] = opp.get("score_band")
        base["opportunity_threshold"] = opp.get("opportunity_threshold")
        base["score_breakdown"] = opp.get("breakdown") or {}
        out.append(base)
    return out


def rank_by_opportunity_score(
    scored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort enriched rows: eligible first by opportunity_score, then confidence."""
    enriched = enrich_scores_with_opportunity(scored)
    enriched.sort(
        key=lambda r: (
            0 if r.get("opportunity_eligible") else 1,
            -int(r.get("opportunity_score") or 0),
            -int(r.get("ai_confidence") or r.get("confidence") or 0),
            -float(r.get("expected_rr") or 0),
            str(r.get("symbol") or "").upper(),
        )
    )
    return enriched
