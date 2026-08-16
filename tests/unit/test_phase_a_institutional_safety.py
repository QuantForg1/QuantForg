"""Phase A institutional safety hardening — unit + failure-injection matrix."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import plan_action
from app.domain.institutional_trading.phase_a.burst_latch import BurstLatch
from app.domain.institutional_trading.phase_a.config import PhaseAConfig
from app.domain.institutional_trading.phase_a.control_vocab import (
    FinalControlState,
    map_to_final_control_state,
)
from app.domain.institutional_trading.phase_a.kill_state import (
    DurableHaltController,
    HaltMode,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataState,
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.phase_a.order_ambiguity import (
    AmbiguityState,
    OrderAmbiguityGate,
)
from app.domain.institutional_trading.phase_a.plane import (
    PhaseAControlPlane,
    reset_phase_a_plane_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_phase_a() -> None:
    reset_phase_a_plane_for_tests()
    yield
    reset_phase_a_plane_for_tests()


# --- A.1 Kill switch -------------------------------------------------------


def test_kill_halt_new_entries_blocks_and_persists() -> None:
    ctrl = DurableHaltController()
    tr = ctrl.set_mode(HaltMode.HALT_NEW_ENTRIES, actor="test", reason="unit")
    assert tr.previous_state == "ACTIVE"
    assert ctrl.new_entries_allowed() is False
    assert ctrl.oms_market_submit_allowed() is False
    assert ctrl.pme_safety_allowed() is True
    assert ctrl.suppress_auto_flatten() is True
    patch = ctrl.to_persist()
    assert patch["phase_a_halt_mode"] == "HALT_NEW_ENTRIES"
    assert patch["kill_switch_armed"] is False

    restored = DurableHaltController()
    restored.hydrate(patch)
    assert restored.mode is HaltMode.HALT_NEW_ENTRIES


def test_kill_halt_all_persists_and_legacy_armed() -> None:
    ctrl = DurableHaltController()
    ctrl.set_mode(HaltMode.HALT_ALL_TRADING, actor="ops", reason="emergency")
    patch = ctrl.to_persist()
    assert patch["kill_switch_armed"] is True
    restored = DurableHaltController()
    restored.hydrate({"kill_switch_armed": True})
    assert restored.mode is HaltMode.HALT_ALL_TRADING


def test_kill_persistence_flag_skips_hydrate_enforcement() -> None:
    plane = PhaseAControlPlane(config=PhaseAConfig(kill_persistence_enabled=False))
    plane.halt.set_mode(HaltMode.ACTIVE, actor="t", reason="reset")
    plane.hydrate(
        {
            "phase_a_halt_mode": "HALT_ALL_TRADING",
            "phase_a_halt_reason": "should_not_apply",
        }
    )
    assert plane.halt.mode is HaltMode.ACTIVE


def test_pme_does_not_auto_flatten_under_phase_a_halt() -> None:
    from app.domain.institutional_trading.phase_a import get_phase_a_plane

    get_phase_a_plane().set_halt(
        HaltMode.HALT_ALL_TRADING, actor="test", reason="no flatten"
    )
    opened = datetime.now(UTC) - timedelta(minutes=5)
    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2000"),
        remaining_volume=Decimal("0.01"),
        initial_volume=Decimal("0.01"),
        initial_stop=Decimal("1990"),
        risk_distance=Decimal("10"),
        opened_at=opened,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("1990"),
        current_tp=Decimal("2020"),
    )
    ctx = PositionManageContext(
        now=datetime.now(UTC),
        current_price=Decimal("2005"),
        atr=Decimal("5"),
        position_still_open=True,
        kill_switch_armed=True,
        user_id=uuid4(),
    )
    action = plan_action(pos, ctx, DEFAULT_PME_CONFIG)
    assert action.kind is not ManageActionKind.DAILY_SHUTDOWN


# --- A.2 UNKNOWN / recon ---------------------------------------------------


def test_unknown_blocks_new_entry_until_reconciled() -> None:
    plane = reset_phase_a_plane_for_tests()
    rec = plane.ambiguity.mark_unknown(
        decision_hash="abc",
        symbol="XAUUSD",
        side="BUY",
        reason="timeout_after_send",
    )
    assert rec.state is AmbiguityState.RECONCILIATION_REQUIRED
    gate = plane.evaluate_new_entry_gate(
        symbol="XAUUSD",
        bid=2000.0,
        ask=2000.1,
        quote_age_seconds=1.0,
    )
    assert gate["allow_new_entry"] is False
    assert "UNKNOWN_ORDER_RECONCILIATION" in str(gate["first_blocking_gate"])

    plane.ambiguity.reconcile_from_mt5(
        rec.order_id,
        position_found=False,
        order_found=False,
        filled=False,
        rejected=True,
    )
    gate2 = plane.evaluate_new_entry_gate(
        symbol="XAUUSD",
        bid=2000.0,
        ask=2000.1,
        quote_age_seconds=1.0,
    )
    assert gate2["allow_new_entry"] is True


def test_recon_gate_flag_disables_block_keeps_record() -> None:
    plane = PhaseAControlPlane(config=PhaseAConfig(recon_gate_enabled=False))
    plane.ambiguity.mark_unknown(
        decision_hash="h", symbol="EURUSD", reason="disconnect"
    )
    assert plane.ambiguity.has_blocking_ambiguity() is True
    gate = plane.evaluate_new_entry_gate(
        symbol="EURUSD", bid=1.1, ask=1.1001, quote_age_seconds=1.0
    )
    assert gate["allow_new_entry"] is True


def test_ambiguity_persist_roundtrip() -> None:
    g = OrderAmbiguityGate()
    g.mark_unknown(decision_hash="d", symbol="XAUUSD", reason="restart")
    raw = g.to_persist()
    g2 = OrderAmbiguityGate()
    g2.hydrate(raw)
    assert g2.has_blocking_ambiguity() is True


# --- A.3 Market data firewall ----------------------------------------------


def test_md_fresh_pass_stale_block() -> None:
    ok = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=2000.0,
        ask=2000.2,
        quote_age_seconds=5.0,
        max_tick_age_seconds=120.0,
        degraded_tick_age_seconds=60.0,
    )
    assert ok.state is MarketDataState.MARKET_DATA_VALID
    assert ok.allow_new_entry is True

    stale = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=2000.0,
        ask=2000.2,
        quote_age_seconds=200.0,
    )
    assert stale.state is MarketDataState.MARKET_DATA_STALE
    assert stale.allow_new_entry is False
    assert stale.first_blocking_gate == "STALE_MARKET_DATA"


@pytest.mark.parametrize(
    "kwargs,gate",
    [
        ({"bid": None, "ask": 1.0, "quote_age_seconds": 1.0}, "QUOTE_MISSING"),
        ({"bid": 0.0, "ask": 1.0, "quote_age_seconds": 1.0}, "QUOTE_MALFORMED"),
        (
            {"bid": 1.0, "ask": 1.1, "quote_age_seconds": None},
            "QUOTE_TIMESTAMP_MISSING",
        ),
        (
            {"bid": 1.0, "ask": 1.1, "quote_age_seconds": 1.0, "market_open": False},
            "MARKET_CLOSED",
        ),
        (
            {"bid": 1.0, "ask": 1.1, "quote_age_seconds": 1.0, "symbol_valid": False},
            "SYMBOL_IDENTITY_INVALID",
        ),
        (
            {"bid": 1.0, "ask": 1.1, "quote_age_seconds": 1.0, "candles_ok": False},
            "CANDLES_STALE_OR_INCOMPLETE",
        ),
    ],
)
def test_md_failure_modes(kwargs: dict, gate: str) -> None:
    v = evaluate_market_data_firewall(symbol="XAUUSD", **kwargs)
    assert v.allow_new_entry is False
    assert v.first_blocking_gate == gate


def test_md_firewall_flag_disables_enforcement() -> None:
    plane = PhaseAControlPlane(config=PhaseAConfig(md_firewall_enabled=False))
    gate = plane.evaluate_new_entry_gate(
        symbol="XAUUSD", bid=None, ask=None, quote_age_seconds=999.0
    )
    assert gate["allow_new_entry"] is True


# --- A.4 Burst latch -------------------------------------------------------


def test_entry_burst_latches() -> None:
    latch = BurstLatch(max_entries_per_minute=3, cooldown_s=60.0)
    assert latch.record_entry_attempt(now=1.0) is None
    assert latch.record_entry_attempt(now=2.0) is None
    ev = latch.record_entry_attempt(now=3.0)
    assert ev is not None
    assert ev.trigger == "entry_burst"
    assert latch.is_latched(now=10.0) is True
    assert latch.is_latched(now=70.0) is False


def test_reject_and_ambiguous_burst() -> None:
    latch = BurstLatch(reject_threshold=2, ambiguous_threshold=2, cooldown_s=30.0)
    latch.record_broker_reject(now=1.0)
    assert latch.record_broker_reject(now=2.0) is not None
    latch2 = BurstLatch(ambiguous_threshold=2, cooldown_s=30.0)
    latch2.record_ambiguous(now=1.0)
    assert latch2.record_ambiguous(now=2.0) is not None


def test_burst_blocks_new_entry_via_plane() -> None:
    import time

    plane = PhaseAControlPlane(
        config=PhaseAConfig(max_entries_per_minute=2, burst_cooldown_seconds=120.0)
    )
    plane.burst.max_entries_per_minute = 2
    now = time.monotonic()
    plane.burst.record_entry_attempt(now=now)
    plane.burst.record_entry_attempt(now=now + 0.01)
    assert plane.burst.is_latched(now=now + 0.02) is True
    gate = plane.evaluate_new_entry_gate(
        symbol="XAUUSD", bid=1.0, ask=1.1, quote_age_seconds=1.0
    )
    assert gate["allow_new_entry"] is False
    assert gate["final_control_state"] == "HALT"


# --- A.5 Control vocabulary ------------------------------------------------


def test_control_vocab_mapping() -> None:
    assert (
        map_to_final_control_state(halt_mode="HALT_NEW_ENTRIES")[0]
        is FinalControlState.HALT
    )
    assert map_to_final_control_state(burst_latched=True)[0] is FinalControlState.HALT
    assert (
        map_to_final_control_state(recon_blocking=True)[0] is FinalControlState.BLOCK
    )
    assert (
        map_to_final_control_state(market_data_allow=False)[0]
        is FinalControlState.BLOCK
    )
    assert (
        map_to_final_control_state(risk_decision="REDUCE")[0]
        is FinalControlState.REDUCE
    )
    assert map_to_final_control_state()[0] is FinalControlState.ALLOW


# --- A.6 Decision journal --------------------------------------------------


def test_decision_journal_records_block() -> None:
    plane = reset_phase_a_plane_for_tests()
    plane.set_halt(HaltMode.HALT_NEW_ENTRIES, actor="t", reason="j")
    plane.evaluate_new_entry_gate(
        symbol="XAUUSD", bid=1.0, ask=1.1, quote_age_seconds=1.0
    )
    recent = plane.journal.recent(1)
    assert recent
    assert recent[0]["final_control_state"] == "HALT"
    assert "KILL_SWITCH" in recent[0]["first_blocking_gate"]


# --- Integration / continuous ops ------------------------------------------


def test_continuous_ops_phase_a_halt() -> None:
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        ContinuousOperationController,
    )
    from app.domain.institutional_trading.phase_a import get_phase_a_plane

    get_phase_a_plane().set_halt(
        HaltMode.HALT_NEW_ENTRIES, actor="t", reason="pause"
    )
    ctrl = ContinuousOperationController()
    d = ctrl.evaluate_new_entry_pause()
    assert d.pause_new_entries is True
    assert d.manage_open_positions is True
    assert any("phase_a" in r for r in d.reasons)
