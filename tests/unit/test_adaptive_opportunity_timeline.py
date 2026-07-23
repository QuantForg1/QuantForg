"""Unit tests — Adaptive Opportunity Timeline (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.adaptive_opportunity_timeline import (
    build_opportunity_timeline,
    predict_trajectory,
    cycle_to_timeline_point,
)


def _cycle(i: int, *, mtf: int, quality: int = 60, confluence: int = 50, lots: str = "0.002"):
    ts = datetime(2026, 7, 23, 12, 0, tzinfo=UTC) + timedelta(minutes=i * 5)
    return {
        "recorded_at": ts.isoformat(),
        "signal_id": f"sig-{i}",
        "decision_action": "NO_TRADE",
        "market_session": "new_york",
        "trend": {
            "aligned": mtf >= 70,
            "score": mtf,
            "h4": "up",
            "h1": "up" if mtf >= 70 else "range",
            "m15": "up",
            "m5": "up",
        },
        "quality": {"score": quality, "required": 75, "passed": quality >= 75},
        "confluence": {
            "total": confluence,
            "required": 75,
            "passed": confluence >= 75,
        },
        "sizing": {
            "raw_lots": lots,
            "approved_lots": "0.00" if float(lots) < 0.01 else "0.01",
            "risk_budget": "1.74",
            "risk_pct": "1.0",
        },
    }


def test_approaching_trade_likely_soon():
    # Mission example: 57 → 60 → 64 → 68 → 71
    cycles = [
        _cycle(0, mtf=57),
        _cycle(1, mtf=60),
        _cycle(2, mtf=64),
        _cycle(3, mtf=68),
        _cycle(4, mtf=71),
    ]
    # newest first (as diagnostics store returns)
    newest_first = list(reversed(cycles))
    payload = build_opportunity_timeline(newest_first, limit=100)
    pred = payload["prediction"]
    assert pred["direction"] == "Approaching Trade"
    assert pred["label"] == "Likely Trade Soon"
    assert pred["mtf_sequence"] == [57, 60, 64, 68, 71]


def test_setup_weakening():
    cycles = [
        _cycle(0, mtf=71),
        _cycle(1, mtf=68),
        _cycle(2, mtf=63),
        _cycle(3, mtf=58),
    ]
    newest_first = list(reversed(cycles))
    pred = build_opportunity_timeline(newest_first)["prediction"]
    assert pred["direction"] == "Moving Away"
    assert pred["label"] == "Setup Weakening"
    assert pred["mtf_sequence"] == [71, 68, 63, 58]


def test_stable_when_flat():
    cycles = [_cycle(i, mtf=55) for i in range(5)]
    pred = predict_trajectory(
        [cycle_to_timeline_point(c) for c in cycles]
    )
    assert pred["direction"] == "Stable"
    assert pred["label"] == "Stable"


def test_timeline_stores_required_fields_and_series():
    cycles = [_cycle(i, mtf=50 + i, quality=55 + i, confluence=40 + i) for i in range(8)]
    newest_first = list(reversed(cycles))
    payload = build_opportunity_timeline(newest_first, limit=100)
    assert payload["mode"] == "adaptive_opportunity_timeline"
    assert payload["never_modifies_strategy_risk_safety_thresholds_oms"] is True
    assert payload["count"] == 8
    point = payload["points"][0]  # newest
    assert "mtf_score" in point
    assert "quality" in point
    assert "confluence" in point
    assert "risk_lots" in point
    assert "opportunity_meter" in point
    assert set(payload["series"]) >= {"mtf", "quality", "confluence", "opportunity"}
    assert len(payload["series"]["mtf"]) == 8


def test_window_caps_at_100():
    cycles = [_cycle(i, mtf=40) for i in range(120)]
    newest_first = list(reversed(cycles))
    payload = build_opportunity_timeline(newest_first, limit=100)
    assert payload["count"] == 100
    assert payload["window"] == 100
