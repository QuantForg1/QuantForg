"""Execution Probability Engine — P(success)/P(failure) from existing AI only.

No external models. No ML rewrite. Uses confidence, RR, and similarity only.
"""

from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def estimate_execution_probability(score: dict[str, Any]) -> dict[str, Any]:
    """Estimate success/failure probabilities from existing AI outputs."""
    confidence = _f(score.get("ai_confidence") or score.get("confidence"), 0.0)
    quality = _f(score.get("trade_quality") or score.get("quality"), 0.0)
    rr = _f(score.get("expected_rr"), 0.0)
    hold = score.get("expected_hold_time") or score.get("expected_hold_minutes")
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    hist_raw = score.get("historical_similarity") or factors.get(
        "historical_similar"
    )
    hist = _f(hist_raw, 50.0)

    # Map institutional confidence/quality into [0.05, 0.95]
    rr_term = min(1.0, max(0.0, (rr - 1.0) / 1.5))
    base = (
        0.35 * (confidence / 100.0)
        + 0.35 * (quality / 100.0)
        + 0.15 * rr_term
        + 0.15 * (hist / 100.0)
    )
    p_success = max(0.05, min(0.95, base))
    if bool(score.get("reject")):
        p_success = min(p_success, 0.25)
    p_failure = max(0.05, min(0.95, 1.0 - p_success))

    # Confidence interval width shrinks with higher confidence/quality
    half = max(0.03, 0.18 - (confidence + quality) / 1000.0)
    ci_low = max(0.01, p_success - half)
    ci_high = min(0.99, p_success + half)

    hold_min: float | None
    try:
        hold_min = float(hold) if hold is not None else None
    except Exception:
        hold_min = None
    if hold_min is None:
        # Soft estimate from confidence (higher confidence → shorter hold)
        hold_min = round(45.0 - (confidence / 100.0) * 20.0, 1)

    return {
        "probability_of_success": round(p_success, 4),
        "probability_of_failure": round(p_failure, 4),
        "estimated_rr": rr if rr > 0 else None,
        "expected_holding_time_minutes": hold_min,
        "confidence_interval": {
            "low": round(ci_low, 4),
            "high": round(ci_high, 4),
            "level": 0.80,
        },
        "inputs": {
            "confidence": confidence,
            "quality": quality,
            "expected_rr": rr,
            "historical_similarity": hist,
        },
        "source": "existing_ai_outputs_only",
        "fabricated": False,
    }
