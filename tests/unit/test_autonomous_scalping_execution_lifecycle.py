"""Autonomous XAUUSD scalping execution lifecycle — TAKE is not a fill.

Does not send orders. Does not lower opportunity/quality/RR floors.
Does not bypass Risk, Safety, or OMS.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.operations.daily_loss_lock import (
    utc_daily_loss_exceeded,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    scan_ineligible_abort_reason,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _ready(**overrides: object) -> GoldExecutionFacts:
    base = dict(
        symbol="XAUUSD_I",
        direction="BUY",
        action="BUY",
        market_open=True,
        tradable=True,
        candles_ok=True,
        bid=Decimal("2400.10"),
        ask=Decimal("2400.30"),
        quote_age_seconds=1.0,
        spread=Decimal("0.20"),
        structure_score=70,
        momentum_score=65,
        quality=80,
        confidence=75,
        pa_confluence=55,
        risk_reward=Decimal("1.20"),
        market_regime="TREND",
        volatility_ok=True,
        session_quality_ok=True,
        safety_allowed=True,
        kill_switch=False,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=True,
        approved_lots=Decimal("0.01"),
        min_lot_infeasible=False,
        portfolio_allow=True,
        optimizer_state="EXECUTE_NOW",
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
        gold_only=True,
        opportunity_score=80,
        opportunity_threshold=70,
    )
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


def _wait_row() -> dict:
    return _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "trade_quality": 52,
            "ai_confidence": 58,
            "opportunity_score": 69,
            "opportunity_threshold": 70,
            "reject": True,
            "reason": "opportunity_score 69 < threshold 70 - WAIT",
            "sniper_entry": {"passed": True, "action": "WAIT"},
        }
    )


def _take_row(side: str) -> dict:
    return _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": side,
            "signal_action": side,
            "trade_quality": 80,
            "ai_confidence": 78,
            "opportunity_score": 80,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": side, "setup_state": "TAKE"},
        }
    )


@pytest.mark.unit
def test_buy_take_may_submit_oms_but_is_not_executed_without_ticket() -> None:
    out = evaluate_gold_execution_contract(_ready(direction="BUY", action="BUY"))
    assert out.may_submit_oms is True
    assert out.stages["RISK"] == "PASS"
    assert out.stages["SAFETY"] == "PASS"
    assert out.stages["OPTIMIZER"] == "PASS"
    assert out.stages["OMS"] == "PASS"
    handoff = build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=None,
    )
    assert handoff["execution_confirmed"] is False


@pytest.mark.unit
def test_sell_take_may_submit_oms_but_is_not_executed_without_ticket() -> None:
    out = evaluate_gold_execution_contract(_ready(direction="SELL", action="SELL"))
    assert out.may_submit_oms is True
    handoff = build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=None,
    )
    assert handoff["execution_confirmed"] is False


@pytest.mark.unit
def test_wait_never_reaches_oms() -> None:
    out = evaluate_gold_execution_contract(
        _ready(opportunity_score=69, action="NO_TRADE")
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    wait = _wait_row()
    over = _overlay_last_ite_cycle(
        wait,
        {
            "forwarded_to_oms": False,
            "abort_reason": "NO_EXECUTABLE_SYMBOL",
            "cycle_outcome": "waiting_next_cycle",
            "mt5_ticket": None,
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["final_decision"] == "WAIT"


@pytest.mark.unit
def test_risk_block_never_reaches_oms() -> None:
    out = evaluate_gold_execution_contract(
        _ready(risk_eligible=False, risk_reasons=("margin insufficient",))
    )
    assert out.may_submit_oms is False
    over = _overlay_last_ite_cycle(
        _take_row("BUY"),
        {
            "forwarded_to_oms": False,
            "abort_reason": "RISK_REJECTED",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "RISK",
                "reason_code": "RISK_REJECTED",
                "human_reason": "margin insufficient",
            },
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["execution_state"] == "EXECUTION_BLOCKED"


@pytest.mark.unit
def test_safety_block_never_reaches_oms() -> None:
    out = evaluate_gold_execution_contract(_ready(kill_switch=True))
    assert out.may_submit_oms is False
    assert out.fault_code == "SAFETY_BLOCKED"
    over = _overlay_last_ite_cycle(
        _take_row("SELL"),
        {
            "forwarded_to_oms": False,
            "abort_reason": "SAFETY_BLOCKED",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "SAFETY",
                "reason_code": "SAFETY_BLOCKED",
                "human_reason": "kill switch armed",
            },
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["safety"] == "BLOCK"


@pytest.mark.unit
def test_stale_quote_never_reaches_oms() -> None:
    out = evaluate_gold_execution_contract(_ready(quote_age_seconds=200.0))
    assert out.may_submit_oms is False
    assert out.fault_code == "STALE_QUOTE"


@pytest.mark.unit
def test_duplicate_signal_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _take_row("BUY"),
        {
            "forwarded_to_oms": False,
            "abort_reason": "DUPLICATE_DECISION",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "OMS",
                "reason_code": "DUPLICATE_DECISION",
                "human_reason": "Duplicate decision hash — execution not allowed",
            },
        },
    )
    assert over["pipeline"]["oms"] == "BLOCK"
    assert over["execution_state"] == "EXECUTION_BLOCKED"
    assert over.get("mt5_ticket") is None


@pytest.mark.unit
def test_xauusd_i_is_accepted() -> None:
    out = evaluate_gold_execution_contract(_ready(symbol="XAUUSD_i"))
    assert out.may_submit_oms is True
    assert str(out.symbol).upper().startswith("XAUUSD")


@pytest.mark.unit
def test_non_xauusd_never_autonomously_submitted() -> None:
    out = evaluate_gold_execution_contract(_ready(symbol="EURUSD_I"))
    assert out.may_submit_oms is False
    assert out.fault_code == "DISABLED_AUTONOMOUS_SYMBOL"


@pytest.mark.unit
def test_min_lot_infeasible_remains_blocked() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=(
                "MIN_LOT_CONSTRAINT: calculated volume below broker volume_min",
            ),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "MIN_LOT_CONSTRAINT"


@pytest.mark.unit
def test_daily_loss_at_or_below_40_is_not_the_old_3_percent_cap() -> None:
    assert MAX_DAILY_LOSS_PCT == Decimal("40.0")
    under = utc_daily_loss_exceeded(
        daily_pnl=Decimal("-39.99"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    at_cap = utc_daily_loss_exceeded(
        daily_pnl=Decimal("-40.00"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    over = utc_daily_loss_exceeded(
        daily_pnl=Decimal("-40.01"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    assert under is False
    assert at_cap is False
    assert over is True
    old_3pct = utc_daily_loss_exceeded(
        daily_pnl=Decimal("-15.21"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    assert old_3pct is False


@pytest.mark.unit
def test_missing_broker_ticket_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _take_row("BUY"),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": None,
            "abort_reason": None,
        },
    )
    assert over["pipeline"]["oms"] == "READY"
    assert over["pipeline"].get("execution_lifecycle") == "EXECUTING"
    assert over.get("execution_state") != "EXECUTED"
    handoff = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=None
    )
    assert handoff["execution_confirmed"] is False


@pytest.mark.unit
def test_oms_rejection_remains_non_executed() -> None:
    over = _overlay_last_ite_cycle(
        _take_row("BUY"),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": None,
            "abort_reason": "OMS_REJECTED",
            "broker_retcode": 10027,
            "execution_blocked": {
                "stage": "OMS",
                "reason_code": "OMS_REJECTED",
                "human_reason": "AutoTrading disabled",
            },
        },
    )
    assert over["pipeline"]["oms"] == "BLOCK"
    assert over["pipeline"]["forwarded_to_oms"] is True
    assert over["pipeline"].get("broker_retcode") == 10027
    assert over.get("execution_state") != "EXECUTED"
    assert over["pipeline"].get("execution_lifecycle") != "FILLED"


@pytest.mark.unit
def test_mt5_rejection_exposes_reason_and_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _take_row("SELL"),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": None,
            "broker_retcode": 10019,
            "abort_reason": "BROKER_REJECTED",
            "execution_blocked": {
                "stage": "BROKER",
                "reason_code": "BROKER_REJECTED",
                "human_reason": "No money",
            },
        },
    )
    assert over["pipeline"]["broker"] == "BLOCK"
    assert over["first_blocker"] == "BROKER_REJECTED"
    assert over.get("execution_state") != "EXECUTED"


@pytest.mark.unit
def test_ticket_confirmation_is_required_for_executed() -> None:
    filled = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=424242
    )
    assert filled["execution_confirmed"] is True
    assert filled["mt5_ticket"] == 424242
    over = _overlay_last_ite_cycle(
        _take_row("BUY"),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": 424242,
            "abort_reason": None,
        },
    )
    assert over["pipeline"]["execution_lifecycle"] == "ORDER_SENT"
    assert over["execution_state"] == "ORDER_SENT"


@pytest.mark.unit
def test_ineligible_scan_is_not_no_executable_symbol() -> None:
    code = scan_ineligible_abort_reason(
        {
            "as_of": "2026-08-27T16:00:00Z",
            "eligible_symbols": [],
            "no_eligible_setup": True,
            "first_blocking_gate": "opportunity_score 69 < threshold 70",
            "opportunity_ranked": [{"symbol": "XAUUSD_I", "opportunity_score": 69}],
        }
    )
    assert code == "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    assert bridge_abort_stage("NO_EXECUTABLE_SYMBOL") == "STRATEGY"
    assert bridge_abort_stage("OPPORTUNITY_SCORE_BELOW_THRESHOLD") == "STRATEGY"
