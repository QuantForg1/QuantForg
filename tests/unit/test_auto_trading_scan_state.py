"""Current scan vs last ITE pipeline — observability only, no order_send."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    blocking_gate_fault_code,
    build_current_scan_decision,
    build_last_pipeline_snapshot,
    classify_candidate_outcome,
    opportunity_window_snapshot,
    publish_current_scan_decision,
    reset_fast_decision_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_VOL_REASON = (
    "Volatility below hard minimum ATR%=0.021 < 0.03 "
    "(evidence dead-tape floor)"
)


def _zero_eligible_scan() -> dict:
    return {
        "as_of": "2026-08-18T19:00:00Z",
        "best_symbol": None,
        "best_candidate": {
            "symbol": "NZDUSD_I",
            "eligible": False,
            "blocking_gate": _VOL_REASON,
            "direction": "NONE",
        },
        "best_eligible_candidate": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "no_eligible_setup": True,
        "first_blocking_gate": _VOL_REASON,
        "opportunity_ranked": [
            {
                "symbol": "NZDUSD_I",
                "opportunity_eligible": False,
                "reject": True,
                "reject_reason": _VOL_REASON,
                "blocking_gate": _VOL_REASON,
                "atr_pct": "0.021",
                "volatility_decision": {
                    "passed": False,
                    "atr_pct": "0.021",
                    "hard_min_pct": "0.03",
                    "band": "low",
                    "reason": _VOL_REASON,
                },
            }
        ],
    }


def _stale_safety_cycle() -> dict:
    return {
        "cycle_outcome": "safety_blocked",
        "abort_reason": "SAFETY_BLOCKED",
        "safety_failed_reasons": ["Open positions 1 at max 1"],
        "decision_action": None,
        "forwarded_to_oms": False,
        "detail": "Open positions 1 at max 1",
        "market_context_diagnostics": {
            "symbol": "XAUUSD",
            "execution_optimizer": {
                "final_state": "EXECUTE_NOW",
                "symbol": "XAUUSD",
                "reason": "stale leftover",
            },
        },
    }


def test_eligible_count_zero_creates_current_scan_state() -> None:
    reset_fast_decision_path()
    decision = build_current_scan_decision(_zero_eligible_scan())
    assert decision["label"] == "CURRENT_SCAN"
    assert decision["state"] == DecisionState.NO_ELIGIBLE_SETUP.value
    assert decision["eligible_count"] == 0
    assert decision["symbol"] == "NZDUSD_I"
    assert decision["blocking_stage"] == "SCANNER"
    assert decision["fault_code"] == "VOLATILITY_HARD_MIN"
    assert decision["fault_reason"] == _VOL_REASON
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert decision["safety_state"] == "NOT_REACHED"
    assert decision["optimizer_state"] == "NOT_RUN"
    assert decision["execution_ready"] is False
    assert decision["forces_trades"] is False


def test_current_scanner_symbol_differs_from_last_pipeline_symbol() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert last is not None
    assert current["current_scan_symbol"] == "NZDUSD_I"
    assert last["last_pipeline_symbol"] == "XAUUSD"
    assert current["current_scan_symbol"] != last["last_pipeline_symbol"]


def test_safety_not_run_when_scan_never_reached_safety() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert current["safety_state"] == "NOT_REACHED"
    assert last is not None
    assert last["safety_state"] == "FAIL"


def test_stale_safety_fail_is_not_current_failure() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert last is not None
    assert last["safety_state"] == "FAIL"
    assert current["safety_state"] != "FAIL"
    assert "SAFETY_BLOCKED" not in str(current.get("fault_code") or "")


def test_optimizer_not_run_when_scan_never_reached_optimizer() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert current["optimizer_state"] == "NOT_RUN"
    assert last is not None
    assert last["optimizer_state"] == "EXECUTE_NOW"
    assert last["last_optimizer_symbol"] == "XAUUSD"


def test_stale_execute_now_is_not_current_optimizer() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    assert current["optimizer_state"] != "EXECUTE_NOW"


def test_first_blocking_gate_comes_from_current_scanner_row() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    assert current["first_blocking_gate"] == _VOL_REASON
    assert "0.03" in str(current["first_blocking_gate"])


def test_full_volatility_detail_is_preserved() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    assert current["atr_pct"] == "0.021"
    assert current["hard_min_pct"] == "0.03"
    assert current["band"] == "low"
    assert current["as_of"] == "2026-08-18T19:00:00Z"
    assert current["atr_source_timeframe"] == "M15"
    assert current["atr_source_period"] == 14
    assert current["symbol"] == "NZDUSD_I"


def test_no_eligible_candidate_is_no_executable_focus() -> None:
    reset_fast_decision_path()
    decision = publish_current_scan_decision(_zero_eligible_scan())
    snap = opportunity_window_snapshot()
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert decision["executable_focus"] is None
    assert snap["current_focus"] is None
    assert snap["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert snap["forces_trades"] is False


def test_window_uses_current_scan_not_stale_ite() -> None:
    reset_fast_decision_path()
    stale = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("Open positions 1 at max 1",),
        cycle_outcome="safety_blocked",
    )
    from app.domain.institutional_trading.operations.fast_decision_path import (
        record_cycle_classification,
        set_focus,
    )

    set_focus("XAUUSD", reason="STALE")
    record_cycle_classification(stale)
    publish_current_scan_decision(_zero_eligible_scan())
    snap = opportunity_window_snapshot()
    assert snap["current_best_candidate"] == "NZDUSD_I"
    assert snap["eligible_count"] == 0
    assert snap["fault_code"] == "VOLATILITY_HARD_MIN"
    assert snap["current_focus"] is None
    assert snap["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_scan_state_module_does_not_submit_orders() -> None:
    src = Path(
        "app/domain/institutional_trading/operations/fast_decision_path.py"
    ).read_text(encoding="utf-8")
    assert "order_send(" not in src
    assert "MetaTrader5" not in src
    assert "forces_trades" in src


def test_atr_below_hard_minimum_normalizes_fault_code() -> None:
    code = blocking_gate_fault_code(_VOL_REASON)
    assert code == "VOLATILITY_HARD_MIN"
    current = build_current_scan_decision(_zero_eligible_scan())
    assert current["fault_code"] == "VOLATILITY_HARD_MIN"
    assert current["fault_reason"] == _VOL_REASON
    assert "0.021" in current["fault_reason"]
    assert "0.03" in current["fault_reason"]
    assert current["state"] == DecisionState.NO_ELIGIBLE_SETUP.value
    assert current["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_atr_at_or_above_hard_minimum_is_not_hard_min_code() -> None:
    passed = "Volatility v2 PASS standard floor=0.03 ATR%=0.031"
    compressed = (
        "Volatility too compressed ATR%=0.04 < exceptional floor 0.05"
    )
    assert blocking_gate_fault_code(passed) != "VOLATILITY_HARD_MIN"
    assert blocking_gate_fault_code(compressed) == "VOLATILITY_COMPRESSED"
    eligible = {
        "as_of": "2026-08-18T19:00:00Z",
        "best_symbol": "XAUUSD_I",
        "best_candidate": {
            "symbol": "XAUUSD_I",
            "eligible": True,
            "blocking_gate": None,
            "direction": "BUY",
        },
        "best_eligible_candidate": {"symbol": "XAUUSD_I", "eligible": True},
        "eligible_count": 1,
        "eligible_symbols": ["XAUUSD_I"],
        "no_eligible_setup": False,
        "first_blocking_gate": None,
        "opportunity_ranked": [
            {
                "symbol": "XAUUSD_I",
                "opportunity_eligible": True,
                "reject": False,
                "direction": "BUY",
                "atr_pct": "0.12",
                "volatility_decision": {
                    "passed": True,
                    "atr_pct": "0.12",
                    "hard_min_pct": "0.03",
                    "band": "normal",
                    "reason": "Volatility v2 PASS standard floor=0.03 ATR%=0.12",
                },
            }
        ],
    }
    current = build_current_scan_decision(eligible)
    assert current["fault_code"] != "VOLATILITY_HARD_MIN"
    assert current["eligible_count"] == 1


def test_best_candidate_is_not_execution_ready() -> None:
    current = build_current_scan_decision(_zero_eligible_scan())
    assert current["best_candidate"]["symbol"] == "NZDUSD_I"
    assert current["best_candidate"]["eligible"] is False
    assert current["best_eligible"] is None
    assert current["execution_ready"] is False
