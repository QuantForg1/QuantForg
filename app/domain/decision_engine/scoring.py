"""Decision Engine — trade score 0–100; default WAIT when insufficient."""

from __future__ import annotations

from typing import Any

# Institutional threshold — most decisions should land WAIT.
MIN_SCORE_FOR_IDEA = 72
MIN_CONFIDENCE_PCT = 70.0


def compute_trade_score(
    *,
    mtf: dict[str, Any],
    structure: dict[str, Any],
    spread_ok: bool | None,
    volatility: str | None,
    session_ok: bool,
    news_risk: str,
    correlation_risk: str,
    portfolio_heat: str,
    execution_quality: str | None,
) -> dict[str, Any]:
    """Score a potential idea. Conservative: start low, earn points, bias to WAIT."""
    score = 28.0
    reasons: list[str] = []
    penalties: list[str] = []

    if mtf.get("aligned"):
        score += 22
        reasons.append(f"MTF aligned {mtf.get('bias')} ({mtf.get('confirmations')} confirms)")
    else:
        penalties.append(str(mtf.get("why") or "MTF not aligned"))
        score -= 8

    conf = float(structure.get("confidence_pct") or 0)
    if conf >= 70:
        score += 12
        reasons.append(f"Structure confidence {conf:.0f}%")
    elif conf >= 55:
        score += 6
        reasons.append(f"Moderate structure confidence {conf:.0f}%")
    else:
        penalties.append(f"Weak structure confidence {conf:.0f}%")
        score -= 6

    trend = str(structure.get("trend") or "Neutral")
    if trend in {"Bullish", "Bearish"} and trend == mtf.get("bias"):
        score += 8
        reasons.append(f"Primary TF trend matches MTF bias ({trend})")
    elif trend == "Neutral":
        penalties.append("Primary structure neutral")
        score -= 5

    if spread_ok is True:
        score += 6
        reasons.append("Spread within ATR tolerance")
    elif spread_ok is False:
        penalties.append("Elevated spread vs ATR")
        score -= 10

    if volatility == "High":
        penalties.append("High volatility regime")
        score -= 6
    elif volatility == "Low":
        score += 3
        reasons.append("Compressed volatility supports cleaner invalidation")

    if session_ok:
        score += 5
        reasons.append("Session context acceptable for liquidity")
    else:
        penalties.append("Session / liquidity context unfavourable")
        score -= 8

    if news_risk == "high":
        penalties.append("High-impact news risk")
        score -= 18
    elif news_risk == "moderate":
        penalties.append("Moderate news proximity")
        score -= 8
    else:
        reasons.append("No elevated news risk from configured calendar")
        score += 4

    if correlation_risk == "high":
        penalties.append("Correlated portfolio exposure elevated")
        score -= 12
    elif correlation_risk == "moderate":
        score -= 5
        penalties.append("Some correlation stacking")
    else:
        score += 3

    if portfolio_heat == "hot":
        penalties.append("Portfolio heat high — capital preservation first")
        score -= 15
    elif portfolio_heat == "warm":
        score -= 6
        penalties.append("Portfolio already engaged")
    else:
        score += 4
        reasons.append("Portfolio capacity available")

    if execution_quality == "weak":
        penalties.append("Recent execution quality weak")
        score -= 8
    elif execution_quality == "strong":
        score += 4
        reasons.append("Execution quality supportive")

    score = max(0.0, min(100.0, score))
    confidence = min(95.0, max(5.0, score * 0.92 + (conf * 0.08 if conf else 0)))

    decision = "WAIT"
    if (
        score >= MIN_SCORE_FOR_IDEA
        and confidence >= MIN_CONFIDENCE_PCT
        and mtf.get("aligned")
        and news_risk != "high"
        and portfolio_heat != "hot"
    ):
        decision = "TRADE_IDEA"

    risk_level = "Elevated"
    if score >= 80 and news_risk == "low":
        risk_level = "Controlled"
    elif score < 55:
        risk_level = "High"

    return {
        "trade_score": round(score, 1),
        "confidence_pct": round(confidence, 1),
        "decision": decision,
        "risk_level": risk_level,
        "thresholds": {
            "min_score": MIN_SCORE_FOR_IDEA,
            "min_confidence_pct": MIN_CONFIDENCE_PCT,
        },
        "supporting_factors": reasons,
        "penalties": penalties,
        "bias_to_wait": decision == "WAIT",
    }
