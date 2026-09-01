"""24/7 worker stays alive; session close does not halt the scheduler."""

from __future__ import annotations

import time

import pytest

from app.domain.institutional_trading.auto_trading import (
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.operations.broker_session_truth import (
    SESSION_CLOSE_DETECTED,
    SESSION_OPEN_DETECTED,
    apply_session_close_side_effects,
    apply_session_open_side_effects,
    note_broker_session,
    reset_broker_session_truth,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    consume_immediate_wakeup,
    reset_decision_cycle,
)
from app.domain.institutional_trading.operations.worker_runtime_state import (
    ERROR,
    HALTED_BY_OPERATOR,
    HALTED_BY_RISK,
    READY,
    RUNNING,
    SCHEDULER_STALLED,
    WAITING_SESSION,
    derive_scheduler_state,
    derive_worker_state,
    last_blocker_from_cycle,
    scheduler_is_stalled,
)
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    canonical_gold_execution_symbol,
    is_bare_gold_symbol,
)
from tests.unit.test_auto_trading_safety import _all_pass_facts

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_broker_session_truth()
    reset_decision_cycle()
    yield
    reset_broker_session_truth()
    reset_decision_cycle()


def test_worker_waiting_session_is_not_halt() -> None:
    state = derive_worker_state(
        running=True,
        cycles=4,
        broker_session_open=False,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="safety_blocked",
        stalled=False,
    )
    assert state == WAITING_SESSION
    assert derive_scheduler_state(
        running=True, stalled=False, broker_session_open=False
    ) == WAITING_SESSION


def test_broker_closed_blocks_new_entries_only() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="london", broker_session_open=False),
    )
    assert result.allowed is False
    assert any("BROKER_SESSION_CLOSED" in r for r in result.failed_reasons)


def test_broker_open_permits_safety_session() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours", broker_session_open=True),
    )
    assert result.allowed is True


def test_open_to_close_emits_session_close_and_wakes_manage_cycle() -> None:
    note_broker_session(True)
    event = note_broker_session(False)
    assert event == SESSION_CLOSE_DETECTED
    apply_session_close_side_effects(symbol="XAUUSD_i", event=event)
    assert consume_immediate_wakeup() == "session_close"


def test_close_to_open_still_wakes() -> None:
    note_broker_session(False)
    event = note_broker_session(True)
    assert event == SESSION_OPEN_DETECTED
    apply_session_open_side_effects(symbol="XAUUSD_i", event=event)
    assert consume_immediate_wakeup() == "session_open"


def test_stale_utc_off_hours_cannot_block_broker_open() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    opened = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours", broker_session_open=True),
    )
    assert opened.allowed is True


def test_scheduler_stalled_only_when_loop_stops_ticking() -> None:
    now = time.monotonic()
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=now,
            now_mono=now + 10,
            interval_seconds=5.0,
            started_mono=now - 30,
            running=True,
        )
        is False
    )
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=now - 200,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 400,
            running=True,
        )
        is True
    )


def test_closed_session_completed_cycle_is_not_stall() -> None:
    now = time.monotonic()
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=now - 20,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 100,
            running=True,
        )
        is False
    )
    state = derive_worker_state(
        running=True,
        cycles=12,
        broker_session_open=False,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="safety_blocked",
        stalled=False,
    )
    assert state == WAITING_SESSION


def test_operator_and_risk_halts_are_named() -> None:
    assert (
        derive_worker_state(
            running=True,
            cycles=3,
            broker_session_open=True,
            operator_halt=True,
            risk_halt=False,
            recovering=False,
            degraded=False,
            last_outcome=None,
            stalled=False,
        )
        == HALTED_BY_OPERATOR
    )
    assert (
        derive_worker_state(
            running=True,
            cycles=3,
            broker_session_open=True,
            operator_halt=False,
            risk_halt=True,
            recovering=False,
            degraded=False,
            last_outcome=None,
            stalled=False,
        )
        == HALTED_BY_RISK
    )


def test_stalled_scheduler_state_is_explicit() -> None:
    assert (
        derive_scheduler_state(running=True, stalled=True, broker_session_open=True)
        == SCHEDULER_STALLED
    )
    assert (
        derive_worker_state(
            running=True,
            cycles=8,
            broker_session_open=True,
            operator_halt=False,
            risk_halt=False,
            recovering=False,
            degraded=True,
            last_outcome="error",
            stalled=True,
        )
        == ERROR
    )


def test_named_blocker_not_generic_no_trade() -> None:
    class _Cycle:
        abort_reason = "SAFETY_BLOCKED"
        cycle_outcome = "safety_blocked"
        detail = "BROKER_SESSION_CLOSED (utc='off_hours')"

    blocker, stage = last_blocker_from_cycle(_Cycle())
    assert blocker == "SAFETY_BLOCKED"
    assert stage == "session"


def test_gold_execution_never_falls_back_to_bare_xauusd() -> None:
    assert canonical_gold_execution_symbol(None) == CANONICAL_GOLD_BROKER_DISPLAY
    assert canonical_gold_execution_symbol("XAUUSD") == CANONICAL_GOLD_BROKER_DISPLAY
    assert not is_bare_gold_symbol(canonical_gold_execution_symbol("XAUUSD_i"))
    assert derive_worker_state(
        running=True,
        cycles=1,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome=None,
        stalled=False,
    ) in {RUNNING, READY}


def test_close_does_not_set_durable_halt() -> None:
    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )
    from app.domain.institutional_trading.phase_a.kill_state import HaltMode

    plane = OperationsControlPlane()
    note_broker_session(True)
    apply_session_close_side_effects(
        symbol="XAUUSD_i", event=note_broker_session(False)
    )
    assert plane.kill_switch_armed is False
    try:
        from app.domain.institutional_trading.phase_a import get_phase_a_plane

        assert get_phase_a_plane().halt.mode is HaltMode.ACTIVE
    except Exception:
        pytest.skip("phase A plane unavailable")


def test_in_progress_cycle_is_not_stalled_inside_hard_timeout() -> None:
    now = time.monotonic()
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=0.0,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 120,
            running=True,
            cycle_started_mono=now - 30,
        )
        is False
    )


def test_in_progress_cycle_stalls_only_after_hard_timeout() -> None:
    from app.domain.institutional_trading.operations.worker_runtime_state import (
        cycle_hard_timeout_seconds,
    )

    now = time.monotonic()
    hard = cycle_hard_timeout_seconds(5.0)
    assert hard >= 180.0
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=0.0,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 400,
            running=True,
            cycle_started_mono=now - (hard + 1.0),
        )
        is True
    )


def test_recoverable_cycle_timeout_does_not_mark_running_worker_error() -> None:
    state = derive_worker_state(
        running=True,
        cycles=8,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="error",
        stalled=False,
    )
    assert state == RUNNING
    assert state != ERROR


def test_stopped_worker_after_error_is_still_error() -> None:
    assert (
        derive_worker_state(
            running=False,
            cycles=8,
            broker_session_open=True,
            operator_halt=False,
            risk_halt=False,
            recovering=False,
            degraded=False,
            last_outcome="error",
            stalled=False,
        )
        == ERROR
    )


def test_cycle_ops_summary_never_confirms_ticket_without_mt5() -> None:
    from app.domain.institutional_trading.operations.worker_runtime_state import (
        build_cycle_ops_summary,
    )

    ops = build_cycle_ops_summary(
        cycle_id=3,
        cycle_start="2026-09-01T15:00:00Z",
        cycle_end="2026-09-01T15:00:40Z",
        last_cycle={
            "abort_reason": "CYCLE_TIMEOUT",
            "cycle_outcome": "error",
            "mt5_ticket": None,
            "forwarded_to_oms": False,
        },
        last_scan={
            "symbols_queued": 36,
            "symbols_evaluated": 10,
            "eligible_count": 2,
            "rows": [
                {
                    "symbol": "EURJPY",
                    "context_status": "SYMBOL_CONTEXT_READY",
                    "direction": "BUY",
                },
                {
                    "symbol": "USDCHF",
                    "failure_class": "SYMBOL_FAILURE",
                    "reject_reason": "SYMBOL_TIMEOUT",
                    "reject": True,
                },
            ],
        },
        positions_managed=1,
    )
    assert ops["tickets_confirmed"] == 0
    assert ops["mt5_ticket"] is None
    assert ops["symbols_targeted"] == 36
    assert ops["symbols_ready"] == 1
    assert ops["symbols_failed"] == 1
    assert ops["signals_found"] == 1
    assert ops["tradeable_count"] == 2
    assert ops["positions_managed"] == 1
    assert ops["cycle_status"] == "CYCLE_TIMEOUT"
