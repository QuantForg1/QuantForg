"""Unit tests — Live Execution Explain Mode (read-only decision cards)."""

from __future__ import annotations

from app.application.services.live_execution_explain import (
    build_execution_explain,
    explain_snapshot_from_diagnostics,
)


def _cycle(**overrides):
    base = {
        "recorded_at": "2026-07-23T12:00:00+00:00",
        "signal_id": "sig-1",
        "decision_action": "NO_TRADE",
        "session_allowed": True,
        "market_session": "LONDON",
        "trend": {"aligned": True, "score": 90},
        "quality": {"score": 78, "required": 75, "passed": True},
        "confluence": {"total": 81, "required": 75, "passed": True},
        "sizing": {"approved_lots": "0.01"},
        "rejection": {"all_codes": [], "primary": None, "primary_label": None},
        "forwarded_to_oms": False,
        "executed": False,
        "abort_reason": "",
        "cycle_outcome": "complete",
    }
    base.update(overrides)
    return base


def test_execute_trade_lists_pass_reasons():
    cycle = _cycle(
        decision_action="BUY",
        forwarded_to_oms=True,
        quality={"score": 78, "required": 75, "passed": True},
        confluence={"total": 81, "required": 75, "passed": True},
        sizing={"approved_lots": "0.01"},
    )
    card = build_execution_explain(cycle)
    assert card["verdict"] == "EXECUTE_TRADE"
    assert card["headline"] == "✅ EXECUTE TRADE"
    assert card["execute_trade"] is True
    assert card["primary_rejection"] is None
    reasons = card["reasons"]
    assert "Session PASS" in reasons
    assert "MTF PASS" in reasons
    assert "Quality 78/75 PASS" in reasons
    assert "Confluence 81/75 PASS" in reasons
    assert "Risk PASS (0.01 lots)" in reasons
    assert "Safety PASS" in reasons


def test_no_trade_first_block_is_mtf():
    cycle = _cycle(
        trend={"aligned": False, "score": 40},
        quality={"score": 50, "required": 75, "passed": False},
        confluence={"total": 50, "required": 75, "passed": False},
    )
    card = build_execution_explain(cycle)
    assert card["verdict"] == "NO_TRADE"
    assert card["headline"] == "❌ NO TRADE"
    assert card["primary_rejection"] == "MTF Alignment FAILED"
    assert card["primary_rejection_detail"] == "MTF Alignment FAILED"
    # Later stages may also fail, but primary is first only
    fails = [s for s in card["stages"] if s["status"] == "FAIL"]
    assert fails[0]["key"] == "mtf"


def test_no_trade_first_block_quality_below_gate():
    cycle = _cycle(
        quality={"score": 74, "required": 75, "passed": False},
        confluence={"total": 80, "required": 75, "passed": True},
    )
    card = build_execution_explain(cycle)
    assert card["primary_rejection_detail"] == "Quality 74 < 75"


def test_no_trade_first_block_confluence_below_gate():
    cycle = _cycle(
        quality={"score": 80, "required": 75, "passed": True},
        confluence={"total": 72, "required": 75, "passed": False},
    )
    card = build_execution_explain(cycle)
    assert card["primary_rejection_detail"] == "Confluence 72 < 75"


def test_no_trade_first_block_risk_zero_lots():
    cycle = _cycle(
        quality={"score": 80, "required": 75, "passed": True},
        confluence={"total": 80, "required": 75, "passed": True},
        sizing={"approved_lots": "0.00"},
    )
    card = build_execution_explain(cycle)
    assert card["primary_rejection_detail"] == "Risk FAILED (approved_lots = 0.00)"


def test_full_trace_includes_all_stages():
    card = build_execution_explain(_cycle())
    keys = [s["key"] for s in card["stages"]]
    assert keys == ["session", "mtf", "quality", "confluence", "risk", "safety"]
    assert card["full_trace_available"] is True
    assert card["mutates_engines"] is False


def test_explain_snapshot_payload_shape():
    diagnostics = {
        "cycles": [_cycle(decision_action="NO_TRADE")],
        "thresholds": {"required_quality": 75, "required_confluence": 75},
    }
    snap = explain_snapshot_from_diagnostics(diagnostics)
    assert snap["mode"] == "live_execution_explain"
    assert snap["never_modifies_strategy_thresholds_risk_safety_oms"] is True
    assert snap["count"] == 1
    assert snap["latest"]["verdict"] == "NO_TRADE"
    assert snap["evaluations"][0]["explain"]["headline"] == "❌ NO TRADE"
