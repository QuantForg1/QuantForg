"""Unit tests — AI Score Calibration audit (evidence only; no threshold changes)."""

from __future__ import annotations

import pytest

from app.application.services.score_calibration_audit import (
    CONFIDENCE_WEIGHTS,
    QUALITY_WEIGHTS,
    counterfactual_perfect_each,
    decompose_cycle,
    run_calibration_audit,
    weighted_total,
)
from app.domain.institutional_trading.config import ITEConfig


@pytest.mark.unit
def test_weights_match_production_sum_100() -> None:
    assert sum(QUALITY_WEIGHTS.values()) == 100
    assert sum(CONFIDENCE_WEIGHTS.values()) == 100


@pytest.mark.unit
def test_thresholds_untouched() -> None:
    cfg = ITEConfig()
    assert cfg.min_confluence_score == 80
    assert cfg.min_trade_quality_score == 80


@pytest.mark.unit
def test_decompose_cycle_confidence_from_engine_factors() -> None:
    cycle = {
        "trace_id": "t1",
        "trend": {
            "h4": "range",
            "h1": "up",
            "m15": "down",
            "m5": "range",
            "aligned": False,
            "score": 42,
        },
        "quality": {"score": 69, "required": 80, "passed": False},
        "confluence": {
            "total": 57,
            "engine_factors": {
                "mtf": 21,
                "m15": 0,
                "structure": 90,
                "liquidity": 20,
                "order_block": 85,
                "fvg": 80,
                "quality": 69,
                "session": 100,
                "news": 100,
                "spread": 93,
                "volatility": 80,
                "drawdown": 80,
            },
        },
        "rejection": {
            "all_codes": ["mtf_not_aligned", "no_liquidity_context"],
            "decision_reasons": [
                "MTF up: H4=range H1=up M15=down M5=range score=42 not aligned",
                "M15 structure events bos=13 choch=11",
                "Latest BOS trend=up",
                "Active order blocks=1",
                "Open FVGs=4",
                "Session tokyo open for 24/7 desk (*2, quality=55, riskx=0.70).",
            ],
        },
    }
    d = decompose_cycle(cycle)
    assert d["confidence"]["components"]["mtf"] == 21
    assert d["confidence"]["components"]["m15"] == 0
    assert d["quality"]["components"]["liquidity"] == 40
    assert d["quality"]["components"]["order_block"] == 75
    assert d["quality"]["components"]["fair_value_gap"] == 85
    assert d["quality"]["components"]["session"] == 55
    # Confidence reconstruction from factors should be near logged total
    assert abs(d["confidence"]["reconstructed_total"] - 57) <= 2


@pytest.mark.unit
def test_counterfactual_perfect_each() -> None:
    scores = {k: 50 for k in QUALITY_WEIGHTS}
    cf = counterfactual_perfect_each(scores, QUALITY_WEIGHTS)
    assert cf["base"] == 50.0
    assert cf["all_perfect"] == 100.0
    assert cf["trend"]["delta"] == pytest.approx(10.0)  # weight 20 → +10 pts


@pytest.mark.unit
def test_audit_does_not_mutate_weights() -> None:
    before_q = dict(QUALITY_WEIGHTS)
    before_c = dict(CONFIDENCE_WEIGHTS)
    cycles = [
        {
            "trace_id": "a",
            "trend": {"score": 42, "aligned": False, "h1": "up"},
            "quality": {"score": 70},
            "confluence": {
                "total": 58,
                "engine_factors": {k: 50 for k in CONFIDENCE_WEIGHTS},
            },
            "rejection": {"all_codes": [], "decision_reasons": []},
        }
    ]
    report = run_calibration_audit(cycles)
    assert report["thresholds_changed"] is False
    assert report["weights_changed"] is False
    assert report["auto_recalibration"] is False
    assert QUALITY_WEIGHTS == before_q
    assert CONFIDENCE_WEIGHTS == before_c
    assert report["cycles_evaluated"] == 1
    assert any(
        r["action"] == "do_not_lower_thresholds" for r in report["recommendations"]
    )


@pytest.mark.unit
def test_weighted_total() -> None:
    assert weighted_total({"a": 100, "b": 0}, {"a": 50, "b": 50}) == 50.0
