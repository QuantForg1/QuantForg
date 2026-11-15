"""Phase 7 Autonomous Trading Control — unit gates."""

from __future__ import annotations

from app.domain.autonomous_trading_control import (
    DEFAULT_MODE,
    ISOLATION_FLAGS,
    MODEL_VERSION,
)
from app.domain.autonomous_trading_control.engines import (
    authorize_execution,
    evaluate_decision,
    propose_sizing,
    select_strategies,
    validate_signal,
)
from app.domain.autonomous_trading_control.store import reset_autonomy_store_for_tests


def setup_function() -> None:
    reset_autonomy_store_for_tests()


def test_isolation_flags_and_default_mode() -> None:
    assert MODEL_VERSION.startswith("phase7-autonomy-")
    assert ISOLATION_FLAGS["never_order_send"] is True
    assert ISOLATION_FLAGS["phase7_live_dispatch"] is False
    assert ISOLATION_FLAGS["default_mode"] == "OBSERVE_ONLY"
    assert DEFAULT_MODE == "OBSERVE_ONLY"
    store = reset_autonomy_store_for_tests()
    assert store.get_mode()["mode"] == "OBSERVE_ONLY"


def test_stale_market_data_yields_no_trade() -> None:
    out = evaluate_decision(
        symbol="XAUUSD",
        direction="BUY",
        confidence=80,
        supporting_evidence=["x"],
        market_data_stale=True,
    )
    assert out["outcome"] == "NO_TRADE"
    assert out["never_order_send"] is True
    assert out["phase7_live_dispatch"] is False


def test_missing_market_data_no_trade() -> None:
    out = evaluate_decision(market_data_missing=True, direction="BUY")
    assert out["outcome"] == "NO_TRADE"


def test_confidence_without_evidence_not_invented() -> None:
    out = evaluate_decision(direction="BUY", confidence=90, supporting_evidence=[])
    assert "confidence_evidence" in out["data_quality"]["missing_fields"]
    assert out["confidence"] is None


def test_strategy_selection_excludes_draft() -> None:
    out = select_strategies(
        candidates=[
            {
                "id": "s1",
                "name": "DraftA",
                "status": "draft",
                "metrics": {"win_rate": 0.7},
            },
            {
                "id": "s2",
                "name": "LiveA",
                "status": "production",
                "approved": True,
                "metrics": {"win_rate": 0.55, "trade_count": 10},
            },
        ]
    )
    assert out["recommended"] is not None
    assert out["recommended"]["strategy_id"] == "s2"
    assert any(e["strategy_id"] == "s1" for e in out["excluded"])
    assert out["rules"]["backtest_alone_not_live"] is True


def test_signal_validation_hard_fail_blocks() -> None:
    out = validate_signal(
        {
            "symbol": "XAUUSD",
            "direction": "BUY",
            "stop_loss": None,
            "strategy_approved": False,
        }
    )
    assert out["blocked"] is True
    assert out["hard_constraint_failed"] is True
    assert len(out["stages"]) >= 15


def test_sizing_refuses_missing_equity() -> None:
    out = propose_sizing({"risk_pct": 1.0})
    assert out["blocked"] is True
    assert out["proposed_lot_size"] is None
    assert "equity" in out["missing_fields"]


def test_sizing_rounds_down_never_invents() -> None:
    out = propose_sizing(
        {
            "equity": 10_000,
            "stop_distance": 10,
            "tick_value": 1,
            "volume_step": 0.01,
            "min_lot": 0.01,
            "max_lot": 1.0,
            "risk_pct": 1.0,
            "authorized_max_lot": 0.5,
        }
    )
    assert out["ok"] is True
    assert out["proposed_lot_size"] is not None
    assert out["proposed_lot_size"] <= 0.5
    assert out["never_increases_risk_limits"] is True


def test_authorize_observe_only_blocks() -> None:
    out = authorize_execution(
        {
            "authenticated": True,
            "account_ownership_verified": True,
            "trade_allowed": True,
            "strategy_approved": True,
            "kill_switch_armed": False,
        }
    )
    assert out["result"] == "BLOCKED"
    assert out["order_send"] is False
    assert out["phase7_live_dispatch"] is False
    assert out["authorized_is_not_live_submit"] is True


def test_mode2_intent_not_live_dispatch() -> None:
    store = reset_autonomy_store_for_tests()
    changed = store.set_mode("CONTROLLED_AUTOMATION", actor="tester", note="intent")
    assert changed["ok"] is True
    assert changed["phase7_live_dispatch"] is False
    out = authorize_execution(
        {
            "authenticated": True,
            "account_ownership_verified": True,
            "trade_allowed": True,
            "strategy_approved": True,
            "kill_switch_armed": False,
            "explicit_automation_authorization": True,
            "validation_blocked": False,
        }
    )
    assert out["result"] == "AUTHORIZED"
    assert out["phase7_live_dispatch"] is False
    assert out["order_send"] is False


def test_approval_material_change_invalidates() -> None:
    store = reset_autonomy_store_for_tests()
    appr = store.create_approval(
        decision_id="dec-1",
        bound_params={
            "symbol": "XAUUSD",
            "direction": "BUY",
            "volume": 0.01,
            "stop_loss": 1,
            "take_profit": 2,
            "account_id": "a1",
        },
        actor="owner",
    )
    bad = store.act_on_approval(
        appr["id"],
        action="Approve",
        actor="owner",
        current_params={
            "symbol": "XAUUSD",
            "direction": "BUY",
            "volume": 0.02,  # changed
            "stop_loss": 1,
            "take_profit": 2,
            "account_id": "a1",
        },
    )
    assert bad is not None
    assert bad.get("ok") is False
    assert bad.get("error") == "material_change"
