"""Unit tests — Adaptive Opportunity Mode (read-only gap analysis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.adaptive_opportunity import (
    MTF_ALIGN_SCORE_NEED,
    build_adaptive_opportunity,
    classify_opportunity_meter,
    estimate_wait_statistics,
    opportunity_snapshot_from_diagnostics,
)


def _cycle(**overrides):
    base = {
        "recorded_at": "2026-07-23T17:46:22+00:00",
        "signal_id": "sig-aom",
        "decision_action": "NO_TRADE",
        "market_session": "new_york",
        "session_allowed": True,
        "trend": {
            "aligned": False,
            "score": 57,
            "h4": "up",
            "h1": "range",
            "m15": "down",
            "m5": "up",
        },
        "quality": {"score": 60, "required": 75, "passed": False},
        "confluence": {"total": 42, "required": 75, "passed": False},
        "sizing": {
            "raw_lots": "0.0018",
            "approved_lots": "0.00",
            "calculated_lots": "0.00",
            "risk_budget": "1.74",
            "risk_pct": "1.0",
            "stop_distance": "9.57",
        },
        "executed": False,
        "forwarded_to_oms": False,
    }
    base.update(overrides)
    return base


def test_gaps_match_mission_example_shape():
    card = build_adaptive_opportunity(_cycle())
    mtf = card["gaps"]["mtf"]
    assert mtf["current"] == 57
    assert mtf["need"] == MTF_ALIGN_SCORE_NEED
    assert mtf["missing"] == MTF_ALIGN_SCORE_NEED - 57
    assert mtf["estimated_h1_candles"] == 2

    q = card["gaps"]["quality"]
    assert q["current"] == 60
    assert q["need"] == 75
    assert q["missing"] == 15

    c = card["gaps"]["confluence"]
    assert c["current"] == 42
    assert c["need"] == 75
    assert c["missing"] == 33

    risk = card["gaps"]["risk"]
    assert risk["current_lots"].startswith("0.0018")
    assert risk["required_lots"] == "0.01"
    # equity ≈ 174 from risk_budget; scale 0.01/0.0018 ≈ 5.56 → ~$790 additional
    assert risk["additional_equity_needed"] is not None
    add = float(risk["additional_equity_needed"])
    assert 780 <= add <= 800


def test_opportunity_meter_red_when_far():
    card = build_adaptive_opportunity(_cycle())
    assert card["opportunity_meter"]["level"] == "RED"
    assert card["opportunity_meter"]["label"] == "Far From Entry"


def test_opportunity_meter_green_on_execute():
    card = build_adaptive_opportunity(
        _cycle(
            decision_action="BUY",
            forwarded_to_oms=True,
            trend={"aligned": True, "score": 90, "h4": "up", "h1": "up"},
            quality={"score": 82, "required": 75, "passed": True},
            confluence={"total": 81, "required": 75, "passed": True},
            sizing={"raw_lots": "0.01", "approved_lots": "0.01"},
        )
    )
    assert card["execute_trade"] is True
    assert card["opportunity_meter"]["level"] == "GREEN"
    assert card["opportunity_meter"]["label"] == "Trade Ready"


def test_opportunity_meter_yellow_almost_ready():
    gaps = [
        {
            "key": "mtf",
            "passed": True,
            "need": 70,
            "missing": 0,
        },
        {
            "key": "quality",
            "passed": False,
            "need": 80,
            "missing": 8,
        },
        {
            "key": "confluence",
            "passed": True,
            "need": 80,
            "missing": 0,
        },
        {
            "key": "risk",
            "passed": True,
            "current_lots": "0.01",
            "required_lots": "0.01",
        },
    ]
    meter = classify_opportunity_meter(execute=False, gaps=gaps)
    assert meter["level"] == "YELLOW"
    assert meter["label"] == "Almost Ready"


def test_wait_statistics_from_history():
    now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
    history = []
    for i in range(10):
        ts = now + timedelta(hours=i * 2)
        action = "BUY" if i in {3, 7} else "NO_TRADE"
        history.append(
            {
                "recorded_at": ts.isoformat(),
                "decision_action": action,
                "executed": action == "BUY",
                "market_session": "new_york" if action == "BUY" else "london",
                "trend": {"aligned": action == "BUY", "score": 80 if action == "BUY" else 50},
                "quality": {
                    "score": 80 if action == "BUY" else 60,
                    "required": 75,
                    "passed": action == "BUY",
                },
                "confluence": {
                    "total": 80 if action == "BUY" else 40,
                    "required": 75,
                    "passed": action == "BUY",
                },
                "sizing": {"raw_lots": "0.01", "approved_lots": "0.01"},
            }
        )
    wait = estimate_wait_statistics(history)
    assert wait["average_waiting_time_hours"] is not None
    assert wait["probability_next_1_hour_pct"] is not None
    assert wait["probability_next_ny_session_pct"] is not None
    assert wait["advisory_only"] is True


def test_snapshot_shape_and_guards():
    snap = opportunity_snapshot_from_diagnostics(
        {"cycles": [_cycle()], "thresholds": {"required_quality": 75}}
    )
    assert snap["mode"] == "adaptive_opportunity"
    assert snap["never_modifies_strategy_thresholds_risk_safety_oms"] is True
    assert snap["latest"]["gaps"]["quality"]["missing"] == 15
    assert snap["mutates_engines"] is False
