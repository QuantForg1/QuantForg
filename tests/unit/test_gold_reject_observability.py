"""Rejected Gold scan must expose the real setup reason — observability only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import SCALPING_V1
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    build_current_scan_decision,
    build_last_pipeline_snapshot,
    named_reject_reasons,
    opportunity_window_snapshot,
    publish_current_scan_decision,
    reset_fast_decision_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
_GOLD = "XAUUSD_I"
_FIRST = "Weak structure score 0 < 60"
_REJECTS = (
    _FIRST,
    "Momentum 0 < 55 — no confirmation",
    "No clear BUY/SELL edge (balanced scores → reject)",
    "Confidence 39 < adaptive 71 (normal)",
    "Trade quality 52 < adaptive 74 (normal)",
    "PA confluence 37 < 45",
)


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


def _rejected_gold_scan(*, generic_gate: bool = True) -> dict:
    return {
        "as_of": "2026-08-19T11:52:00Z",
        "best_symbol": None,
        "best_candidate": {
            "symbol": _GOLD,
            "eligible": False,
            "direction": "NONE",
            "quality": 52,
            "confidence": 39,
        },
        "best_eligible_candidate": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "no_eligible_setup": True,
        "first_blocking_gate": "NO_ELIGIBLE_SETUP" if generic_gate else _FIRST,
        "opportunity_ranked": [
            {
                "symbol": _GOLD,
                "opportunity_eligible": False,
                "eligible": False,
                "reject": True,
                "direction": "NONE",
                "quality": 52,
                "confidence": 39,
                "reject_reason": "; ".join(_REJECTS),
                "reject_reasons": list(_REJECTS),
                "blocking_gate": "; ".join(_REJECTS),
                "atr_pct": "0.122",
                "volatility_decision": {
                    "passed": True,
                    "atr_pct": "0.122",
                    "hard_min_pct": "0.08",
                    "band": "normal",
                    "reason": "ok",
                },
                "thresholds": {"band": "normal", "hard_min_pct": "0.08"},
            }
        ],
    }


def _stale_ite_cycle() -> dict:
    return {
        "cycle_outcome": "no_trade",
        "abort_reason": "NO_ELIGIBLE_SETUP",
        "safety_failed_reasons": [],
        "decision_action": "NO_TRADE",
        "forwarded_to_oms": False,
        "market_context_diagnostics": {
            "symbol": "XAUUSD",
            "execution_optimizer": {
                "final_state": "EXECUTE_NOW",
                "symbol": "XAUUSD",
            },
        },
    }


def test_rejected_gold_row_becomes_current_best_candidate(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["symbol"] == _GOLD
    assert decision["best_candidate"]["symbol"] == _GOLD
    assert decision["best_candidate"]["eligible"] is False
    assert decision["best_eligible"] is None


def test_reject_reasons_zero_becomes_first_blocking_gate(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["first_blocking_gate"] == _FIRST
    assert decision["fault_reason"] == _FIRST
    assert decision["first_blocking_gate"] != "NO_ELIGIBLE_SETUP"
    assert named_reject_reasons(decision)[0] == _FIRST


def test_atr_remains_visible_on_rejected_gold(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["atr_pct"] == "0.122"
    assert decision["hard_min_pct"] == "0.08"
    assert decision["band"] == "normal"
    assert decision["atr_source_timeframe"] == "M15"
    assert decision["as_of"] == "2026-08-19T11:52:00Z"


def test_eligible_count_remains_zero(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["eligible_count"] == 0
    assert decision["eligible_symbols"] == []


def test_execution_ready_remains_false(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["execution_ready"] is False
    assert decision["executable_focus"] is None
    assert decision["forces_trades"] is False


def test_next_action_is_no_executable_focus(gold_only: None) -> None:
    reset_fast_decision_path()
    decision = publish_current_scan_decision(_rejected_gold_scan())
    snap = opportunity_window_snapshot()
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert snap["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert snap["current_focus"] is None
    assert snap["first_blocking_gate"] == _FIRST


def test_current_scan_safety_is_not_reached(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["safety_state"] == "NOT_REACHED"
    assert decision["optimizer_state"] == "NOT_RUN"


def test_last_pipeline_remains_separate(gold_only: None) -> None:
    current = build_current_scan_decision(_rejected_gold_scan())
    last = build_last_pipeline_snapshot(_stale_ite_cycle())
    assert last is not None
    assert current["label"] == "CURRENT_SCAN"
    assert last["label"] == "LAST_COMPLETED_ITE_CYCLE"
    assert current["first_blocking_gate"] == _FIRST
    assert current["safety_state"] == "NOT_REACHED"
    assert last["cycle_outcome"] == "no_trade"
    assert current["optimizer_state"] != last.get("optimizer_state")


def test_all_reject_reasons_are_preserved(gold_only: None) -> None:
    decision = build_current_scan_decision(_rejected_gold_scan())
    assert decision["all_reject_reasons"] == list(_REJECTS)
    assert decision["all_reject_reasons"][0] == _FIRST


def test_gold_broker_form_found_when_catalogue_spelling_differs(
    gold_only: None,
) -> None:
    scan = _rejected_gold_scan()
    scan["best_candidate"] = {"symbol": "EURUSD_I", "eligible": True}
    scan["eligible_symbols"] = ["EURUSD_I"]
    scan["opportunity_ranked"][0]["symbol"] = "XAUUSD_I"
    decision = build_current_scan_decision(scan)
    assert decision["symbol"] == "XAUUSD_I"
    assert decision["eligible_count"] == 0
    assert decision["first_blocking_gate"] == _FIRST
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_generic_gate_only_when_no_rejected_row(gold_only: None) -> None:
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-19T11:52:00Z",
            "best_symbol": None,
            "eligible_symbols": [],
            "opportunity_ranked": [],
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
        }
    )
    assert decision["symbol"] is None
    assert decision["first_blocking_gate"] == "NO_ELIGIBLE_SETUP"
    assert decision["atr_pct"] is None
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_scalping_v1_floors_unchanged() -> None:
    assert SCALPING_V1.min_structure_score == 60
    assert SCALPING_V1.min_momentum_score == 55
    assert SCALPING_V1.normal_vol.quality == 74
    assert SCALPING_V1.normal_vol.confidence == 71
    assert SCALPING_V1.min_pa_confluence_score == 45
    gates = (
        ROOT / "app/domain/institutional_trading/ai_scalping/quality_gates.py"
    ).read_text(encoding="utf-8")
    profile = (
        ROOT / "app/domain/institutional_trading/ai_scalping/profiles/scalping_v1.py"
    ).read_text(encoding="utf-8")
    assert "min_structure_score=60" in profile
    assert "min_momentum_score=55" in profile
    assert "quality=74" in profile
    assert "confidence=71" in profile
    assert "min_pa_confluence_score=45" in profile
    assert "Weak structure score" in gates


def test_observability_modules_do_not_send_orders() -> None:
    for rel in (
        "app/domain/institutional_trading/operations/fast_decision_path.py",
        "app/application/services/institutional_multi_asset_scanner.py",
        "frontend/src/components/ops/auto-trading-workspace.tsx",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "order_send(" not in src
        assert "MetaTrader5" not in src
        assert "OrderSend" not in src
