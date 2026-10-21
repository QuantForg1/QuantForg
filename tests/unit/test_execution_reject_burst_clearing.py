"""EXECUTION_REJECT_BURST: how it arms, what never arms it, and how it clears."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.execution.models import OmsSubmitResult
from app.domain.institutional_trading.phase_a.burst_latch import BurstLatch
from app.domain.institutional_trading.phase_a.execution_reject import (
    apply_oms_outcome_to_burst,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _gateway_disabled() -> OmsSubmitResult:
    # What production saw while MT5_GATEWAY_EXECUTION_ENABLED=false.
    return OmsSubmitResult(
        outcome="disabled",
        message="MT5 retcode 90001: gateway execution disabled",
        retcode=90001,
    )


def _accepted() -> OmsSubmitResult:
    return OmsSubmitResult(
        outcome="success",
        message="filled",
        retcode=10009,
        order_ticket=1,
        gateway_status="order_send_ok",
    )


def test_gateway_failures_arm_the_burst_and_cooldown_clears_it() -> None:
    latch = BurstLatch()
    t0 = 1_000.0
    for i in range(latch.ambiguous_threshold):
        latch.record_ambiguous(now=t0 + i, stage="GATEWAY")
    assert latch.is_latched(now=t0 + 3)
    assert latch.blocking_gate_name() == "EXECUTION_REJECT_BURST"
    # Clears on its own once the cooldown after the last arming has passed.
    release = t0 + (latch.ambiguous_threshold - 1) + latch.cooldown_s
    assert latch.is_latched(now=release - 1)
    assert not latch.is_latched(now=release + 1)
    assert latch.remaining_cooldown_s(now=release + 1) == 0.0


def test_gateway_disabled_reply_never_arms_the_burst() -> None:
    latch = BurstLatch()
    for _ in range(50):
        apply_oms_outcome_to_burst(
            latch,
            abort_reason="EXECUTION_DISABLED",
            status="OMS_FAILURE",
            oms_result=_gateway_disabled(),
        )
    assert not latch.is_latched()
    snap = latch.snapshot()
    assert snap["rejected_entries_last_window"] == 0
    assert snap["execution_failures_last_window"] == 0


def test_accepted_orders_after_enable_do_not_rearm() -> None:
    latch = BurstLatch()
    for _ in range(3):
        apply_oms_outcome_to_burst(
            latch,
            abort_reason="NONE",
            status="OMS_SUCCESS",
            oms_result=_accepted(),
        )
    # Owner limit is one entry per cycle — far below the 6/min entry burst.
    assert not latch.is_latched()
    assert latch.snapshot()["blocking_gate"] is None


def test_genuine_mt5_rejects_arm_after_threshold() -> None:
    latch = BurstLatch()
    rejected = OmsSubmitResult(outcome="rejected", message="no money", retcode=10019)
    for _ in range(latch.reject_threshold):
        apply_oms_outcome_to_burst(
            latch,
            abort_reason="MT5_REJECTION",
            status="OMS_REJECTED",
            oms_result=rejected,
        )
    assert latch.is_latched()
    assert latch.blocking_gate_name() == "EXECUTION_REJECT_BURST"


def test_snapshot_states_the_clear_condition() -> None:
    snap = BurstLatch().snapshot()
    assert "cooldown" in snap["reject_burst"]["clear_condition"]
    assert "fill not required" in snap["reject_burst"]["clear_condition"]
