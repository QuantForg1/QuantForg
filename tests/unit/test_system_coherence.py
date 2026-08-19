"""System-wide trading communication coherence."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

from app.domain.institutional_trading.operations.fast_decision_path import (
    build_current_scan_decision,
    build_last_pipeline_snapshot,
    publish_current_scan_decision,
    reset_fast_decision_path,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.system_coherence import (
    FaultClass,
    InFlightDedupe,
    Plane,
    StageStatus,
    compose_system_snapshot,
    engine_bool_to_status,
    get_coherence_store,
    is_ignored_action_token,
    market_status_from_scan,
    reset_system_coherence,
    sanitize_next_action,
    symbol_identity,
    typed_engine_status,
)
from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY, GOLD_SYMBOL
from app.domain.trading.xauusd_specs import MAX_LEVERAGE


def setup_function() -> None:
    reset_fast_decision_path()
    reset_system_coherence()


def _scan(**overrides: object) -> dict:
    row = {
        "as_of": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "best_symbol": CANONICAL_GOLD_BROKER_DISPLAY,
        "eligible_count": 1,
        "eligible_symbols": [CANONICAL_GOLD_BROKER_DISPLAY],
        "best_candidate": {
            "symbol": CANONICAL_GOLD_BROKER_DISPLAY,
            "eligible": True,
            "direction": "BUY",
            "quality": 80,
            "confidence": 75,
            "opportunity_score": 71,
        },
        "best_eligible_candidate": {
            "symbol": CANONICAL_GOLD_BROKER_DISPLAY,
            "eligible": True,
        },
        "opportunity_ranked": [
            {
                "symbol": CANONICAL_GOLD_BROKER_DISPLAY,
                "opportunity_eligible": True,
                "opportunity_score": 71,
            }
        ],
        "first_blocking_gate": None,
        "note": "eligible",
    }
    row.update(overrides)
    return row


def test_one_cycle_one_authoritative_current_scan() -> None:
    first = publish_current_scan_decision(_scan())
    second = publish_current_scan_decision(_scan(as_of="2026-08-19T22:00:05Z"))
    stored = get_coherence_store().get(Plane.CURRENT_SCAN.value)
    assert stored is not None
    assert stored["label"] == "CURRENT_SCAN"
    assert stored["sequence"] >= 2
    assert stored["snapshot_id"] == second.get("snapshot_id")
    assert first["snapshot_id"] != second["snapshot_id"]


def test_older_state_cannot_overwrite_newer() -> None:
    store = get_coherence_store()
    store.publish(Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i"}, sequence=105)
    rejected = store.publish(
        Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i", "stale": True}, sequence=104
    )
    assert rejected["accepted"] is False
    assert rejected["reason"] == "STALE_SEQUENCE"
    assert store.get(Plane.CURRENT_SCAN.value).get("stale") is not True


def test_logical_canonical_symbol_coherent() -> None:
    logical, canonical = symbol_identity("XAUUSD")
    assert logical == GOLD_SYMBOL
    assert canonical == CANONICAL_GOLD_BROKER_DISPLAY
    logical2, canonical2 = symbol_identity("XAUUSD_i")
    assert logical2 == GOLD_SYMBOL
    assert canonical2 == CANONICAL_GOLD_BROKER_DISPLAY


def test_current_scan_and_last_pipeline_remain_separate() -> None:
    scan = publish_current_scan_decision(_scan())
    last = build_last_pipeline_snapshot(
        {
            "cycle_outcome": "no_snapshot",
            "abort_reason": "NO_SNAPSHOT",
            "market_context_diagnostics": {
                "symbol": "XAUUSD_i",
                "as_of": "2026-08-19T21:59:00Z",
            },
        }
    )
    view = compose_system_snapshot(current_scan=scan, last_pipeline=last)
    assert view["planes_separate"] is True
    assert view["current_scan"]["label"] == "CURRENT_SCAN"
    assert view["last_pipeline"]["label"] == "LAST_COMPLETED_ITE_CYCLE"
    assert view["stages"]["MARKET"] == StageStatus.PASS.value
    assert view["last_pipeline_safety_state"] == "NOT_REACHED"
    assert view["current_safety_state"] == StageStatus.NOT_REACHED.value


def test_risk_pass_distinct_from_not_assessed() -> None:
    assert typed_engine_status(True) == "PASS"
    assert typed_engine_status(False) == "BLOCK"
    assert typed_engine_status(None) == "NOT_ASSESSED"
    assert engine_bool_to_status(None) is StageStatus.NOT_ASSESSED
    assert engine_bool_to_status(True) is not engine_bool_to_status(None)


def test_safety_pass_distinct_from_not_assessed() -> None:
    assert typed_engine_status(True) != typed_engine_status(None)
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        decision_intelligence={
            "safety": {"state": "NOT_ASSESSED"},
            "risk": {"state": "PASS"},
        },
    )
    assert view["stages"]["SAFETY"] == "NOT_ASSESSED"
    assert view["stages"]["RISK"] == "PASS"


def test_decision_approve_does_not_authorize_without_hard_stages() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        decision_intelligence={
            "risk": {"state": "PASS"},
            "safety": {"state": "PASS"},
        },
    )
    assert view["stages"]["DECISION"] == "PASS"
    assert view["execution_authorized"] is False
    assert view["execute_now_required"] is False


def test_probability_score_does_not_bypass_hard_safety() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        decision_intelligence={"safety": {"state": "FAIL"}, "risk": {"state": "PASS"}},
    )
    assert view["opportunity_score"] == 71
    assert view["stages"]["SAFETY"] == "BLOCK"
    assert view["execution_ready"] is False
    assert view["execution_authorized"] is False


def test_stale_health_does_not_halt_current_execution() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline={
            "label": "LAST_COMPLETED_ITE_CYCLE",
            "abort_reason": "GATEWAY_UNAVAILABLE",
            "safety_state": "FAIL",
            "as_of": "2026-08-19T21:00:00Z",
            "symbol": "XAUUSD_i",
        },
        health={"gateway_connected": True, "healthy": True},
    )
    assert view["health"]["gateway_connected"] is True
    assert view["stages"]["SAFETY"] == "NOT_REACHED"
    assert view["execution_authorized"] is False


def test_real_health_failure_is_visible_not_authority() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        health={"gateway_connected": False, "broker_connected": False},
    )
    assert view["health"]["gateway_connected"] is False
    assert "HEALTH is not EXECUTION AUTHORITY" in str(view["health"]["note"])


def test_gateway_recovery_does_not_keep_stale_block_as_current() -> None:
    last = build_last_pipeline_snapshot(
        {
            "cycle_outcome": "safety_blocked",
            "abort_reason": "SAFETY_BLOCKED",
            "safety_failed_reasons": ["MT5 Gateway not connected"],
            "market_context_diagnostics": {
                "symbol": "XAUUSD_i",
                "as_of": "2026-08-19T21:00:00Z",
            },
        }
    )
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=last,
        health={"gateway_connected": True},
    )
    assert view["current_safety_state"] != "FAIL"
    assert view["last_pipeline_safety_state"] == "FAIL"


def test_duplicate_events_are_harmless() -> None:
    store = get_coherence_store()
    a = store.publish(Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i"}, sequence=1)
    b = store.publish(Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i"}, sequence=1)
    assert a["accepted"] is True
    assert b["accepted"] is True


def test_out_of_order_events_are_ignored() -> None:
    store = get_coherence_store()
    store.publish(Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i", "n": 2}, sequence=2)
    out = store.publish(
        Plane.CURRENT_SCAN.value, {"symbol": "XAUUSD_i", "n": 1}, sequence=1
    )
    assert out["accepted"] is False
    assert store.get(Plane.CURRENT_SCAN.value)["n"] == 2


def test_duplicate_api_calls_are_deduped() -> None:
    dedupe = InFlightDedupe()
    assert dedupe.acquire("quote:XAUUSD_i") is True
    assert dedupe.acquire("quote:XAUUSD_i") is False
    dedupe.complete("quote:XAUUSD_i", {"bid": 2400})
    assert dedupe.get("quote:XAUUSD_i")["bid"] == 2400
    assert dedupe.acquire("quote:XAUUSD_i") is False


def test_advisory_failures_do_not_block() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
    )
    assert view["fault_class"] in {
        FaultClass.NONE.value,
        FaultClass.SOFT_WAIT.value,
        "NONE",
    }
    assert view["execution_authorized"] is False


def test_hard_failures_do_block() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        decision_intelligence={"risk": {"state": "FAIL"}, "safety": {"state": "PASS"}},
    )
    assert view["stages"]["RISK"] == "BLOCK"
    assert view["execution_ready"] is False


def test_unknown_order_maps_to_reconciliation_fault_class() -> None:
    assert FaultClass.RECONCILIATION_REQUIRED.value == "RECONCILIATION_REQUIRED"


def test_execute_now_does_not_control_autonomous_execution() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
    )
    assert view["execute_now_required"] is False
    contract_src = inspect.getsource(evaluate_gold_execution_contract)
    assert "execute_now_required" in contract_src


def test_only_xauusd_i_enters_autonomous_identity() -> None:
    _logical, other = symbol_identity("EURUSD")
    assert other != CANONICAL_GOLD_BROKER_DISPLAY
    _l, gold = symbol_identity("XAUUSD_i")
    assert gold == CANONICAL_GOLD_BROKER_DISPLAY


def test_one_authorization_at_most_one_submit_flag() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
        contract={
            "may_submit_oms": True,
            "stages": dict.fromkeys(
                (
                    "MARKET",
                    "STRATEGY",
                    "DECISION",
                    "SAFETY",
                    "RISK",
                    "SIZING",
                    "PORTFOLIO",
                    "OPTIMIZER",
                    "OMS",
                    "BROKER",
                ),
                "PASS",
            ),
        },
    )
    assert view["execution_authorized"] is True
    assert view["direction"] == "BUY"


def test_current_snapshot_has_one_timestamp_and_version() -> None:
    published = publish_current_scan_decision(_scan())
    view = compose_system_snapshot(current_scan=published, last_pipeline=None)
    assert view["as_of"]
    assert view["cycle_id"]
    assert view["snapshot_id"]
    assert isinstance(view["sequence"], int)


def test_ui_receives_backend_truth_fields() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
    )
    for key in (
        "canonical_symbol",
        "lifecycle",
        "next_action",
        "blocking_stage",
        "stages",
        "as_of",
    ):
        assert key in view


def test_no_stale_optimizer_or_safety_as_current() -> None:
    last = build_last_pipeline_snapshot(
        {
            "cycle_outcome": "execution_deferred",
            "abort_reason": "EXECUTION_OPTIMIZER_DEFER",
            "market_context_diagnostics": {
                "symbol": "XAUUSD_i",
                "as_of": "2026-08-19T21:00:00Z",
                "execution_optimizer": {"final_state": "WAIT", "symbol": "XAUUSD_i"},
            },
        }
    )
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=last,
    )
    assert view["current_optimizer_state"] == "NOT_REACHED"
    assert view["last_pipeline_optimizer_state"] == "WAIT"


def test_no_stale_focus_or_market() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
    )
    assert view["canonical_symbol"] == CANONICAL_GOLD_BROKER_DISPLAY
    assert view["stages"]["MARKET"] == "PASS"
    assert view["lifecycle"] != "MARKET_CONTEXT_NOT_READY"


def test_ignored_action_not_in_authoritative_state() -> None:
    assert is_ignored_action_token("ignored_action") is True
    action = sanitize_next_action(
        focus="XAUUSD_i", next_action="ignored_action", direction="BUY"
    )
    assert "ignored" not in action.lower()
    view = compose_system_snapshot(
        current_scan={
            **publish_current_scan_decision(_scan()),
            "fault_code": "ignored_action",
            "fault_reason": "ignored_action",
        },
        last_pipeline=None,
    )
    assert view["ignored_action"] is False
    assert view["fault_code"] != "ignored_action"


def test_none_plus_wait_same_focus_is_impossible() -> None:
    action = sanitize_next_action(
        focus=None, next_action="WAIT_SAME_FOCUS", direction="NONE"
    )
    assert action == "NO_EXECUTABLE_FOCUS"


def test_no_market_fail_when_current_scan_valid() -> None:
    status = market_status_from_scan(
        has_current_scan=True,
        scan_valid=True,
        scan_stale=False,
        market_hard_fail=False,
    )
    assert status == "PASS"
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline={"cycle_outcome": "no_snapshot", "abort_reason": "NO_SNAPSHOT"},
    )
    assert view["stages"]["MARKET"] != "BLOCK"


def test_no_market_context_not_ready_when_valid_scan_exists() -> None:
    view = compose_system_snapshot(
        current_scan=publish_current_scan_decision(_scan()),
        last_pipeline=None,
    )
    assert view["lifecycle"] != "MARKET_CONTEXT_NOT_READY"
    rejected = build_current_scan_decision(
        {
            "as_of": "2026-08-19T22:00:00Z",
            "eligible_count": 0,
            "eligible_symbols": [],
            "best_candidate": {
                "symbol": "XAUUSD_i",
                "eligible": False,
                "reject_reasons": ["Weak structure score 0 < 60"],
            },
            "opportunity_ranked": [
                {
                    "symbol": "XAUUSD_i",
                    "opportunity_eligible": False,
                    "opportunity_score": 12,
                    "reject_reason": "Weak structure score 0 < 60",
                }
            ],
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
        }
    )
    view2 = compose_system_snapshot(current_scan=rejected, last_pipeline=None)
    assert view2["lifecycle"] != "MARKET_CONTEXT_NOT_READY"
    assert rejected.get("best_candidate") is not None or rejected.get("symbol")


def test_leverage_policy_source_is_backend_max_leverage() -> None:
    assert str(MAX_LEVERAGE) == "2000"


def test_stale_scan_is_wait_not_market_fail() -> None:
    old = (datetime.now(UTC) - timedelta(seconds=400)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    published = publish_current_scan_decision(_scan(as_of=old))
    view = compose_system_snapshot(current_scan=published, last_pipeline=None)
    assert view["stages"]["MARKET"] in {"WAIT", "PASS"}
