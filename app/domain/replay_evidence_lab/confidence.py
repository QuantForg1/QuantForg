"""Confidence scoring for institutional evidence KPIs — advisory only."""

from __future__ import annotations

from typing import Any

from app.domain.replay_evidence_lab.models import ConfidenceLevel


def confidence_level(sample_size: int) -> ConfidenceLevel:
    """Map sample size to confidence. Never inflates samples."""
    n = max(0, int(sample_size))
    if n < 30:
        return "insufficient"
    if n < 100:
        return "low"
    if n < 300:
        return "medium"
    return "high"


def coverage_ratio(*, observed: int, required: int) -> float | None:
    if required <= 0:
        return None
    return round(min(1.0, max(0.0, observed / required)), 4)


def score_kpi(
    *,
    name: str,
    value: Any,
    sample_size: int,
    required_sample: int,
) -> dict[str, Any]:
    """Attach sample size, confidence, and coverage to a KPI value."""
    n = max(0, int(sample_size))
    req = max(0, int(required_sample))
    level = confidence_level(n)
    cov = coverage_ratio(observed=n, required=req) if req else None
    return {
        "name": name,
        "value": value,
        "sample_size": n,
        "confidence": level,
        "coverage": cov,
        "required_sample": req if req else None,
        "status": "available" if value is not None and n > 0 else "unavailable",
    }


def build_confidence_report(
    *,
    kpis: list[dict[str, Any]],
    live_closed_trades: int,
    replay_opportunities: int,
    no_trade_observations: int,
    thresholds: dict[str, int],
) -> dict[str, Any]:
    scored_kpis = [k for k in kpis if isinstance(k, dict)]

    bottleneck = min(
        live_closed_trades,
        replay_opportunities,
        no_trade_observations,
    )
    overall = (
        confidence_level(bottleneck)
        if (
            live_closed_trades > 0
            and replay_opportunities > 0
            and no_trade_observations > 0
        )
        else "insufficient"
    )

    return {
        "status": "available",
        "overall_confidence": overall,
        "kpis": scored_kpis,
        "lane_samples": {
            "live_closed_trades": {
                "sample_size": live_closed_trades,
                "confidence": confidence_level(live_closed_trades),
                "coverage": coverage_ratio(
                    observed=live_closed_trades,
                    required=thresholds.get("min_live_closed_trades", 50),
                ),
            },
            "replay_opportunities": {
                "sample_size": replay_opportunities,
                "confidence": confidence_level(replay_opportunities),
                "coverage": coverage_ratio(
                    observed=replay_opportunities,
                    required=thresholds.get("min_replay_opportunities", 500),
                ),
            },
            "no_trade_observations": {
                "sample_size": no_trade_observations,
                "confidence": confidence_level(no_trade_observations),
                "coverage": coverage_ratio(
                    observed=no_trade_observations,
                    required=thresholds.get("min_no_trade_observations", 100),
                ),
            },
        },
        "note": "Confidence is advisory — never upgrades fabricated samples",
    }
