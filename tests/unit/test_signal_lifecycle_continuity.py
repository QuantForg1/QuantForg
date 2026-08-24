"""Signal lifecycle: never silently drop a valid blocked candidate."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.signal_center_service import (
    _execution_classification,
    _is_min_lot_constraint,
)
from app.application.services.strategy_performance_telemetry import (
    get_strategy_performance_telemetry,
    reset_strategy_performance_telemetry,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    get_symbol_state_book,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    classify_post_ai_execution_chain,
)
from app.domain.institutional_trading.operations.signal_lifecycle import (
    SIGNAL_BLOCKED_MIN_LOT,
    SIGNAL_BLOCKED_SAME_SYMBOL,
    SIGNAL_CLOSED,
    SIGNAL_EXECUTED,
    SIGNAL_FOUND,
    classify_signal_final_state,
    is_high_quality_signal,
)
from app.domain.institutional_trading.operations.worker_runtime_state import (
    HALTED_BY_RISK,
    RUNNING,
    derive_worker_state,
    last_blocker_from_cycle,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _hq_signal(*, direction: str = "BUY") -> dict:
    return {
        "symbol": "XAUUSD_i",
        "direction": direction,
        "confidence": 82,
        "signal_quality": 92,
        "strategy_id": "SCALPING_V1",
        "trade_class": "SCALP",
        "approved_stop": "13.3846",
        "min_lot_feasibility": "MIN_LOT_INFEASIBLE",
    }


def test_strong_buy_min_lot_is_blocked_not_silent_no_trade() -> None:
    state = classify_signal_final_state(
        direction="BUY",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        reasons="MIN_LOT_CONSTRAINT",
        eligible=False,
    )
    assert state == SIGNAL_BLOCKED_MIN_LOT
    assert state != "NO_TRADE"
    assert is_high_quality_signal(direction="BUY", quality=92, confidence=82)


def test_strong_sell_min_lot_is_blocked_not_silent_no_trade() -> None:
    state = classify_signal_final_state(
        direction="SELL",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_CONSTRAINT",
        eligible=False,
    )
    assert state == SIGNAL_BLOCKED_MIN_LOT


def test_blocked_signal_does_not_halt_worker() -> None:
    state = derive_worker_state(
        running=True,
        cycles=12,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="execution_contract",
        stalled=False,
    )
    assert state == RUNNING
    assert state != HALTED_BY_RISK
    class _Cycle:
        abort_reason = "MIN_LOT_INFEASIBLE"
        cycle_outcome = "execution_contract"
        detail = "MIN_LOT_CONSTRAINT"
    blocker, stage = last_blocker_from_cycle(_Cycle())
    assert blocker == "MIN_LOT_INFEASIBLE"
    assert stage == "risk"


def test_next_cycle_still_runs_after_min_lot_block() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_cycle(
        cycle_key="cyc-1",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        this_cycle_forwarded=False,
        signal=_hq_signal(),
    )
    store.observe_cycle(
        cycle_key="cyc-2",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        this_cycle_forwarded=False,
        signal=_hq_signal(),
    )
    snap = store.snapshot()
    assert snap["blocked_signals"] == 2
    assert snap["blocked_by_min_lot"] == 2
    assert {r["cycle_id"] for r in snap["recent_lifecycle"]} == {"cyc-1", "cyc-2"}


def test_same_symbol_block_is_not_durable_halt() -> None:
    state = classify_signal_final_state(
        direction="BUY",
        forwarded_to_oms=False,
        fault_code="QUANTFORG_SAME_SYMBOL_OPEN",
        reasons="already open QuantForg XAUUSD_i",
    )
    assert state == SIGNAL_BLOCKED_SAME_SYMBOL
    worker = derive_worker_state(
        running=True,
        cycles=4,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="execution_contract",
        stalled=False,
    )
    assert worker == RUNNING


def test_position_close_releases_stale_same_symbol_state() -> None:
    book = get_symbol_state_book()
    book.reset()
    book.note_reject("XAUUSD_I")
    book.reset("XAUUSD_I")
    assert "XAUUSD_I" not in book.snapshot()["symbols"]
    rt = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
    )
    rt._eligible_consumed = {"XAUUSD_I"}
    rt._eligible_handoff_queue = []
    rt._eligible_consumed = set()
    rt._eligible_handoff_queue = ["XAUUSD_I"]
    rt._entries_this_scan = 0
    assert rt._take_next_handoff_symbol() == "XAUUSD_I"


def test_later_candidate_remains_discoverable() -> None:
    """A blocked cycle must not permanently consume the gold candidate.

    The next scan rebuilds the handoff queue with consumed cleared.
    """
    rt = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
    )
    rt._eligible_handoff_queue = ["XAUUSD_I"]
    rt._eligible_consumed = {"XAUUSD_I"}
    rt._entries_this_scan = 1
    assert rt._take_next_handoff_symbol() is None
    rt._eligible_consumed = set()
    rt._entries_this_scan = 0
    assert rt._take_next_handoff_symbol() == "XAUUSD_I"


def test_blocked_signal_records_exact_blocker() -> None:
    reset_strategy_performance_telemetry()
    row = get_strategy_performance_telemetry().observe_cycle(
        cycle_key="cyc-block",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_CONSTRAINT",
        this_cycle_forwarded=False,
        signal=_hq_signal(direction="BUY"),
        reasons="MIN_LOT_INFEASIBLE",
    )
    assert row["final_state"] == SIGNAL_BLOCKED_MIN_LOT
    assert row["final_blocker"] == "MIN_LOT_CONSTRAINT"
    assert row["direction"] == "BUY"
    assert row["high_quality"] is True
    miss = get_strategy_performance_telemetry().snapshot()["high_quality_near_misses"]
    assert miss[0]["confidence"] == 82
    assert miss[0]["quality"] == 92
    assert miss[0]["final_blocker"] == "MIN_LOT_CONSTRAINT"


def test_stale_signal_is_not_reused() -> None:
    reset_strategy_performance_telemetry()
    row = get_strategy_performance_telemetry().observe_cycle(
        cycle_key="cyc-stale",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        ticket="562442610",
        this_cycle_forwarded=False,
        signal=_hq_signal(),
    )
    assert row["ticket"] is None
    assert row["stale_ticket_reused"] is False
    assert row["freshness"] == "STALE_ATTEMPT"
    snap = get_strategy_performance_telemetry().snapshot()
    assert snap["stale_signal_count"] == 1


def test_blocked_cycle_has_no_oms_gateway_mt5() -> None:
    chain = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        blocking_stage="RISK",
        ticket="999",
        retcode=10009,
        this_cycle_forwarded=False,
    )
    assert chain["oms_submit"] == "NOT_ATTEMPTED"
    assert chain["mt5_gateway"] == "NOT_ATTEMPTED"
    assert chain["ticket"] is None
    assert chain["forwarded_to_oms"] is False


def test_successful_execution_state_unchanged() -> None:
    assert (
        classify_signal_final_state(
            direction="BUY",
            forwarded_to_oms=True,
            eligible=True,
        )
        == SIGNAL_EXECUTED
    )
    chain = classify_post_ai_execution_chain(
        forwarded_to_oms=True,
        this_cycle_forwarded=True,
        ticket="12345",
        retcode=10009,
    )
    assert chain["oms_submit"] == "PASS"
    assert chain["ticket"] == "12345"


def test_telemetry_counts_blocked_signals() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_cycle(
        cycle_key=str(uuid4()),
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        this_cycle_forwarded=False,
        signal=_hq_signal(),
    )
    store.observe_cycle(
        cycle_key=str(uuid4()),
        forwarded_to_oms=False,
        blocking_stage="SAFETY",
        fault_code="SAFETY_BLOCKED",
        this_cycle_forwarded=False,
        signal=_hq_signal(direction="SELL"),
    )
    snap = store.snapshot()
    assert snap["high_quality_signals"] == 2
    assert snap["blocked_signals"] == 2
    assert snap["blocked_by_min_lot"] == 1
    assert snap["blocked_by_safety"] == 1
    assert snap["executed_signals"] == 0
    assert _is_min_lot_constraint("MIN_LOT_INFEASIBLE: stop exceeds max")
    cls = _execution_classification(
        direction="BUY",
        reject=True,
        reason="MIN_LOT_INFEASIBLE",
        quality=92,
        confidence=82,
    )
    assert cls["signal_state"] == "VALID_SIGNAL"
    assert cls["block_code"] == "MIN_LOT_CONSTRAINT"


def test_closed_lifecycle_does_not_count_as_block() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_fill(ticket="1", direction="BUY", signal_quality=90, confidence=80)
    store.observe_close(ticket="1", realized_pnl="1.0", realized_r="0.4")
    snap = store.snapshot()
    assert snap["blocked_signals"] == 0
    assert any(r["final_state"] == SIGNAL_CLOSED for r in snap["recent_lifecycle"])
    assert classify_signal_final_state(closed=True) == SIGNAL_CLOSED
    assert classify_signal_final_state(direction="BUY") == SIGNAL_FOUND
