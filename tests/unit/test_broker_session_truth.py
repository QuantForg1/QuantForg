"""Broker session truth — UTC off_hours must not override an open broker."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.institutional_trading.auto_trading import (
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import SessionFilterResult
from app.domain.institutional_trading.operations.broker_session_truth import (
    BROKER_SESSION_CLOSED,
    BROKER_SESSION_OPEN,
    SESSION_CLOSE_DETECTED,
    SESSION_OPEN_DETECTED,
    SESSION_STATE_INCONSISTENCY,
    classify_broker_session_open,
    note_broker_session,
    overlay_snapshot_session,
    reset_broker_session_truth,
    resolve_from_diagnostics,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    consume_immediate_wakeup,
    reset_decision_cycle,
)
from app.domain.institutional_trading.session_filter import SessionFilter
from app.domain.market_context.enums import MarketSession
from tests.unit.test_auto_trading_safety import _all_pass_facts

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture(autouse=True)
def _reset_session_state() -> None:
    reset_broker_session_truth()
    reset_decision_cycle()
    yield
    reset_broker_session_truth()
    reset_decision_cycle()


def test_broker_closed_blocks_even_if_utc_london() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="london", broker_session_open=False),
    )
    assert result.allowed is False
    assert any("BROKER_SESSION_CLOSED" in r for r in result.failed_reasons)


def test_broker_open_unblocks_utc_off_hours() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    blocked = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours"),
    )
    assert blocked.allowed is False
    opened = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours", broker_session_open=True),
    )
    assert opened.allowed is True
    session_cond = next(c for c in opened.conditions if c.key == "trading_session")
    assert SESSION_STATE_INCONSISTENCY in session_cond.detail


def test_unknown_broker_keeps_utc_off_hours_block() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours", broker_session_open=None),
    )
    assert result.allowed is False
    assert any("off_hours" in r for r in result.failed_reasons)


def test_classify_full_trade_mode_is_open() -> None:
    assert (
        classify_broker_session_open(
            trade_mode="full",
            trade_allowed=True,
            market_data_live=True,
        )
        is True
    )


def test_classify_closeonly_is_closed() -> None:
    assert (
        classify_broker_session_open(
            trade_mode="closeonly",
            trade_allowed=False,
            market_data_live=True,
        )
        is False
    )


def test_session_closed_to_open_wakes_cycle() -> None:
    from app.domain.institutional_trading.operations.broker_session_truth import (
        apply_session_open_side_effects,
    )

    note_broker_session(False)
    event = note_broker_session(True)
    assert event == SESSION_OPEN_DETECTED
    apply_session_open_side_effects(symbol="XAUUSD_i", event=event)
    assert consume_immediate_wakeup() == "session_open"


def test_first_open_observation_wakes_cycle() -> None:
    from app.domain.institutional_trading.operations.broker_session_truth import (
        apply_session_open_side_effects,
    )

    event = note_broker_session(True)
    assert event == SESSION_OPEN_DETECTED
    apply_session_open_side_effects(symbol="XAUUSD_i", event=event)
    assert consume_immediate_wakeup() == "session_open"


def test_control_plane_forwards_broker_session_open() -> None:
    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )

    plane = OperationsControlPlane()
    plane.auto_trading_enabled = True
    plane.auto_trading_run_state = "running"
    blocked = plane.evaluate_auto_trading(_all_pass_facts(session="off_hours"))
    session_block = next(c for c in blocked.conditions if c.key == "trading_session")
    assert session_block.passed is False

    opened = plane.evaluate_auto_trading(
        _all_pass_facts(session="off_hours", broker_session_open=True)
    )
    session_open = next(c for c in opened.conditions if c.key == "trading_session")
    assert session_open.passed is True
    assert SESSION_STATE_INCONSISTENCY in session_open.detail


def test_resolve_diagnostics_sunday_full_gold() -> None:
    snap = resolve_from_diagnostics(
        {
            "symbol_trade_mode": "full",
            "symbol_trade_allowed": True,
            "server_time": "2026-08-23T16:00:00Z",
        },
        utc_session="off_hours",
        symbol_tradable=True,
        market_data_live=True,
    )
    assert snap.broker_session == BROKER_SESSION_OPEN
    assert snap.safety_allowed is True
    assert snap.inconsistency is True
    assert snap.session_source == "broker_symbol_trade_mode"


def test_overlay_allows_eligibility_when_broker_open() -> None:
    from dataclasses import dataclass

    inner = SessionFilterResult(
        session=MarketSession.OFF_HOURS,
        allowed=False,
        reason="Session off_hours is outside tradable market windows",
        quality_score=40,
        stars=1,
    )

    @dataclass(frozen=True)
    class Snap:
        session: SessionFilterResult
        symbol: str = "XAUUSD_i"

    out = overlay_snapshot_session(Snap(session=inner), broker_open=True)
    assert out.session.allowed is True
    assert "BROKER_SESSION_OPEN" in out.session.reason


def test_utc_weekend_classifier_still_off_hours() -> None:
    result = SessionFilter(config=ITEConfig()).evaluate(
        as_of=datetime(2026, 8, 23, 16, 0, tzinfo=UTC)
    )
    assert result.session is MarketSession.OFF_HOURS
    assert result.allowed is False


def test_session_open_to_close_emits_close_detected() -> None:
    from app.domain.institutional_trading.operations.broker_session_truth import (
        apply_session_close_side_effects,
    )

    note_broker_session(True)
    event = note_broker_session(False)
    assert event == SESSION_CLOSE_DETECTED
    apply_session_close_side_effects(symbol="XAUUSD_i", event=event)
    assert consume_immediate_wakeup() == "session_close"


def test_closeonly_diagnostics_remain_closed() -> None:
    snap = resolve_from_diagnostics(
        {"symbol_trade_mode": "closeonly", "symbol_trade_allowed": False},
        utc_session="london",
        symbol_tradable=True,
        market_data_live=True,
    )
    assert snap.broker_session == BROKER_SESSION_CLOSED
    assert snap.safety_allowed is False
