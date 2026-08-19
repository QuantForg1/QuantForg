"""Opportunity window must not treat ignored_action as a current trading fault."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.execution.models import BridgeAbortReason
from app.domain.institutional_trading.operations.fast_decision_path import (
    NO_CURRENT_BLOCK,
    NO_CURRENT_BLOCKING_GATE,
    CandidateAction,
    DecisionState,
    build_current_scan_decision,
    build_last_pipeline_snapshot,
    classify_candidate_outcome,
    coherent_next_action,
    is_ignored_action_value,
    opportunity_window_snapshot,
    publish_current_scan_decision,
    record_cycle_classification,
    reset_fast_decision_path,
    sanitize_blocking_gate,
    sanitize_fault_code,
    set_focus,
)
from app.domain.trading.gold_only import GOLD_SYMBOL, is_gold_symbol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
_GOLD = "XAUUSD_I"
_VOL = "Volatility below hard minimum ATR%=0.021 < 0.03 (evidence dead-tape floor)"


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


def _gold_rejected_scan() -> dict:
    return {
        "as_of": "2026-08-19T03:00:00Z",
        "best_symbol": None,
        "best_candidate": {
            "symbol": _GOLD,
            "eligible": False,
            "blocking_gate": _VOL,
            "direction": "NONE",
        },
        "best_eligible_candidate": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "no_eligible_setup": True,
        "first_blocking_gate": _VOL,
        "opportunity_ranked": [
            {
                "symbol": _GOLD,
                "opportunity_eligible": False,
                "reject": True,
                "reject_reason": _VOL,
                "blocking_gate": _VOL,
                "atr_pct": "0.021",
                "volatility_decision": {
                    "passed": False,
                    "atr_pct": "0.021",
                    "hard_min_pct": "0.03",
                    "band": "low",
                    "reason": _VOL,
                },
            }
        ],
    }


def _unevaluated_scan() -> dict:
    return {
        "as_of": "2026-08-19T03:00:00Z",
        "best_symbol": None,
        "best_candidate": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "opportunity_ranked": [],
    }


def _gold_eligible_scan() -> dict:
    return {
        "as_of": "2026-08-19T03:00:00Z",
        "best_symbol": _GOLD,
        "best_candidate": {
            "symbol": _GOLD,
            "eligible": True,
            "blocking_gate": None,
            "direction": "BUY",
        },
        "best_eligible_candidate": {"symbol": _GOLD, "eligible": True},
        "eligible_count": 1,
        "eligible_symbols": [_GOLD],
        "opportunity_ranked": [
            {"symbol": _GOLD, "opportunity_score": 70, "eligible": True}
        ],
    }


def _stale_safety_cycle() -> dict:
    return {
        "cycle_outcome": "safety_blocked",
        "abort_reason": "SAFETY_BLOCKED",
        "safety_failed_reasons": ["Open positions 1 at max 1"],
        "decision_action": None,
        "forwarded_to_oms": False,
        "market_context_diagnostics": {
            "symbol": _GOLD,
            "execution_optimizer": {
                "final_state": "EXECUTE_NOW",
                "symbol": _GOLD,
                "reason": "stale leftover",
            },
        },
    }


def _assert_no_ignored_action(snap: dict) -> None:
    blob = str(snap)
    assert "ignored_action" not in blob.lower().replace("-", "_")
    for key in ("blocking_gate", "first_blocking_gate", "fault_code", "next_action"):
        assert not is_ignored_action_value(snap.get(key))
        assert str(snap.get(key) or "").lower() != "ignored_action"


def test_ignored_action_never_becomes_blocking_gate(gold_only: None) -> None:
    out = classify_candidate_outcome(
        abort_reason=BridgeAbortReason.IGNORED_ACTION.value,
        decision_action="NO_TRADE",
        cycle_outcome="no_trade",
    )
    assert out["fault_code"] != "ignored_action"
    assert out["fault_reason"] != "ignored_action"
    assert out["next_action"] != CandidateAction.WAIT_SAME_FOCUS.value
    assert sanitize_blocking_gate("ignored_action") == NO_CURRENT_BLOCKING_GATE
    reset_fast_decision_path()
    for _ in range(51):
        record_cycle_classification(out)
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    _assert_no_ignored_action(snap)
    assert snap["blocking_gate"] != "ignored_action"
    assert snap["first_blocking_gate"] != "ignored_action"


def test_ignored_action_never_becomes_fault_code(gold_only: None) -> None:
    assert sanitize_fault_code("ignored_action") == NO_CURRENT_BLOCK
    assert sanitize_fault_code("ignored_action WATCH") == NO_CURRENT_BLOCK
    reset_fast_decision_path()
    cls = classify_candidate_outcome(
        abort_reason="ignored_action",
        decision_action="WATCH",
    )
    record_cycle_classification(cls)
    snap = opportunity_window_snapshot()
    assert snap["fault_code"] != "ignored_action"
    assert snap["fault_code"] in {NO_CURRENT_BLOCK, "NO_ELIGIBLE_SETUP"}


def test_ignored_action_never_becomes_next_action(gold_only: None) -> None:
    nxt = coherent_next_action(current_focus=None, next_action="ignored_action")
    assert nxt != "ignored_action"
    assert nxt == CandidateAction.NO_EXECUTABLE_FOCUS.value
    out = classify_candidate_outcome(abort_reason="ignored_action")
    assert out["next_action"] != "ignored_action"


def test_none_plus_wait_same_focus_is_impossible(gold_only: None) -> None:
    reset_fast_decision_path()
    set_focus(None, reason="NONE")
    record_cycle_classification(
        {
            "decision_state": DecisionState.SETUP_NOT_READY.value,
            "fault_code": "ignored_action",
            "fault_reason": "ignored_action",
            "next_action": CandidateAction.WAIT_SAME_FOCUS.value,
        }
    )
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    assert snap["current_focus"] is None
    assert snap["next_action"] != CandidateAction.WAIT_SAME_FOCUS.value
    assert snap["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_none_plus_no_executable_focus_is_valid(gold_only: None) -> None:
    reset_fast_decision_path()
    decision = publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    assert decision["executable_focus"] is None
    assert snap["current_focus"] is None
    assert snap["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert snap["setup_state"] == DecisionState.SETUP_NOT_READY.value
    assert snap["eligible_count"] == 0


def test_gold_focus_wait_same_focus_only_with_active_gold(gold_only: None) -> None:
    reset_fast_decision_path()
    set_focus(_GOLD, reason="HOLD_FOCUS")
    decision = publish_current_scan_decision(_gold_eligible_scan())
    snap = opportunity_window_snapshot()
    assert is_gold_symbol(str(decision.get("executable_focus") or ""))
    assert snap["current_focus"] == _GOLD
    assert snap["next_action"] == CandidateAction.WAIT_SAME_FOCUS.value
    assert snap["setup_state"] in {
        DecisionState.WAITING.value,
        DecisionState.FOCUS_FORMING.value,
        DecisionState.EXECUTION_READY.value,
    }
    none_wait = coherent_next_action(
        current_focus=None,
        next_action=CandidateAction.WAIT_SAME_FOCUS.value,
    )
    assert none_wait == CandidateAction.NO_EXECUTABLE_FOCUS.value
    gold_wait = coherent_next_action(
        current_focus=_GOLD,
        next_action=CandidateAction.WAIT_SAME_FOCUS.value,
    )
    assert gold_wait == CandidateAction.WAIT_SAME_FOCUS.value


def test_current_scan_safety_not_inherited_from_last_ite(gold_only: None) -> None:
    current = build_current_scan_decision(_gold_rejected_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert current["safety_state"] == "NOT_REACHED"
    assert last is not None
    assert last["safety_state"] == "FAIL"
    reset_fast_decision_path()
    record_cycle_classification(
        classify_candidate_outcome(
            abort_reason="SAFETY_BLOCKED",
            failed_reasons=("Open positions 1 at max 1",),
            cycle_outcome="safety_blocked",
        )
    )
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    assert snap["safety_state"] == "NOT_REACHED"
    assert snap["fault_code"] != "SAFETY_BLOCKED"


def test_current_scan_optimizer_not_inherited_from_last_ite(gold_only: None) -> None:
    current = build_current_scan_decision(_gold_rejected_scan())
    last = build_last_pipeline_snapshot(_stale_safety_cycle())
    assert current["optimizer_state"] == "NOT_RUN"
    assert last is not None
    assert last["optimizer_state"] == "EXECUTE_NOW"
    reset_fast_decision_path()
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    assert snap["optimizer_state"] == "NOT_RUN"
    assert snap["optimizer_state"] != "EXECUTE_NOW"


def test_current_opportunity_snapshot_is_internally_consistent(gold_only: None) -> None:
    reset_fast_decision_path()
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    required = {
        "snapshot_id",
        "as_of",
        "symbol",
        "current_focus",
        "best_candidate",
        "eligible_count",
        "setup_state",
        "blocking_stage",
        "fault_class",
        "fault_code",
        "fault_reason",
        "next_action",
        "safety_state",
        "optimizer_state",
        "cycle_latency_ms",
    }
    assert required.issubset(snap.keys())
    assert snap["as_of"] == "2026-08-19T03:00:00Z"
    assert snap["snapshot_id"]
    assert snap["symbol"] == _GOLD
    assert snap["best_candidate"] == _GOLD
    assert snap["eligible_count"] == 0
    assert snap["execution_ready"] is False
    if snap["current_focus"] is None:
        assert snap["next_action"] != CandidateAction.WAIT_SAME_FOCUS.value
    if snap["next_action"] == CandidateAction.WAIT_SAME_FOCUS.value:
        assert is_gold_symbol(str(snap["current_focus"] or ""))
    _assert_no_ignored_action(snap)
    assert snap["primary_blockers"] == []


def test_gold_only_mode_remains_unchanged(gold_only: None) -> None:
    from app.domain.trading.gold_only import gold_only_enabled

    assert gold_only_enabled() is True
    src = (ROOT / "app/domain/trading/gold_only.py").read_text(encoding="utf-8")
    assert "def gold_only_enabled" in src
    assert "settings.gold_only_mode" in src


def test_no_non_gold_candidate_in_current_scan(gold_only: None) -> None:
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-19T03:00:00Z",
            "best_symbol": "EURUSD_I",
            "best_candidate": {
                "symbol": "EURUSD_I",
                "eligible": True,
                "direction": "BUY",
            },
            "eligible_count": 1,
            "eligible_symbols": ["EURUSD_I", "GBPUSD_I"],
            "opportunity_ranked": [
                {"symbol": "EURUSD_I", "opportunity_score": 90, "eligible": True},
                {"symbol": "GBPUSD_I", "opportunity_score": 80, "eligible": True},
            ],
        }
    )
    symbol = str(decision.get("symbol") or "")
    assert not symbol or is_gold_symbol(symbol)
    assert decision["executable_focus"] in {None, _GOLD, GOLD_SYMBOL, "XAUUSD_i"}
    reset_fast_decision_path()
    publish_current_scan_decision(decision)
    snap = opportunity_window_snapshot()
    focus = str(snap.get("current_focus") or "")
    best = str(snap.get("best_candidate") or "")
    assert not focus or is_gold_symbol(focus)
    assert not best or is_gold_symbol(best)


def test_unevaluated_gold_is_none_not_fabricated(gold_only: None) -> None:
    decision = build_current_scan_decision(_unevaluated_scan())
    assert decision["symbol"] is None
    assert decision["best_candidate"] is None
    assert decision["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_no_safety_risk_oms_gateway_order_send_changes() -> None:
    frozen = [
        ROOT / "app/domain/institutional_trading/execution/models.py",
        ROOT / "app/domain/institutional_trading/execution/bridge.py",
        ROOT / "app/infrastructure/brokers/mt5/gateway_client.py",
        ROOT / "app/domain/trading/gold_only.py",
    ]
    models = (ROOT / "app/domain/institutional_trading/execution/models.py").read_text(
        encoding="utf-8"
    )
    assert 'IGNORED_ACTION = "ignored_action"' in models
    for path in frozen:
        text = path.read_text(encoding="utf-8")
        if path.name == "gateway_client.py":
            assert "Never retry order_send" in text
            assert "order_send" in text
    runtime = (ROOT / "app/application/services/institutional_ite_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "OrderSend" not in runtime
    path_src = (
        ROOT / "app/domain/institutional_trading/operations/fast_decision_path.py"
    ).read_text(encoding="utf-8")
    assert "order_send(" not in path_src
    assert "forces_trades" in path_src


def test_event_counter_is_not_current_blocking_gate(gold_only: None) -> None:
    reset_fast_decision_path()
    ignored = classify_candidate_outcome(
        abort_reason="ignored_action",
        decision_action="NO_TRADE",
    )
    for _ in range(51):
        record_cycle_classification(ignored)
    record_cycle_classification(
        classify_candidate_outcome(
            abort_reason="SAFETY_BLOCKED",
            failed_reasons=("Open positions 1 at max 1",),
            cycle_outcome="safety_blocked",
        )
    )
    publish_current_scan_decision(_gold_rejected_scan())
    snap = opportunity_window_snapshot()
    codes = {str(row.get("fault_code")) for row in snap.get("primary_blockers") or []}
    assert "ignored_action" not in codes
    assert snap["blocking_gate"] != "ignored_action"
    assert "ignored_action:" not in str(snap.get("fault_reason") or "")
    assert snap["safety_state"] != "FAIL"
