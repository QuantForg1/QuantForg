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
    """Weighted Opportunity Score 0–100 from existing production metrics only."""
    c = compute_opportunity_components(score)
    # Weights sum to 100 — keep existing AI quality/confidence dominant
    weights = {
        "ai_quality": 14,
        "confidence": 14,
        "mtf_alignment": 9,
        "liquidity": 7,
        "volatility": 7,
        "spread_quality": 6,
        "session_quality": 5,
        "news_risk": 4,
        "trend_strength": 6,
        "structure_quality": 5,
        "order_block_quality": 4,
        "fvg_quality": 3,
        "risk_reward": 5,
        "execution_probability": 11,
    }
    total_w = sum(weights.values()) or 1
    raw = sum(c[k] * weights[k] for k in weights) / total_w
    reject = bool(score.get("reject"))
    direction = str(score.get("direction") or "NONE").upper()
    if reject or direction not in {"BUY", "SELL"}:
        # Keep score for ranking visibility but mark ineligible
        opportunity = int(_clamp(raw * 0.55))
        eligible = False
    else:
        opportunity = int(_clamp(raw))
        eligible = opportunity > 0
    return {
        "opportunity_score": opportunity,
        "components": c,
        "eligible": eligible and not reject and direction in {"BUY", "SELL"},
        "symbol": str(score.get("symbol") or "").upper(),
        "direction": direction,
        "reject": reject,
        "blocking_gate": score.get("reject_reason") or score.get("blocking_gate"),
        "weights": weights,
        "fabricated": False,
        "source": "existing_ai_scalping_score",
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
