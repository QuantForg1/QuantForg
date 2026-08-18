"""Soft vs hard execution halt classification — no Safety/Risk threshold change."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.continuous_operation import (
    ContinuousOperationController,
)
from app.domain.institutional_trading.operations.execution_halt_policy import (
    HaltClass,
    classify_halt_condition,
    does_not_halt_new_entry,
    halts_new_entry,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.phase_a.order_ambiguity import (
    AmbiguityState,
    OrderAmbiguityGate,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_ADVISORY = (
    "UI/telemetry stale",
    "duplicate health probe",
    "optional enrichment unavailable",
    "non-authoritative analytics unavailable",
    "Ops telemetry delayed",
    "stale heartbeat:execution",
    "Connected (cached)",
)

_HARD = (
    "MT5 disconnected",
    "Gateway unavailable",
    "stale quote",
    "invalid symbol",
    "risk limit exceeded",
    "Safety failure",
    "minimum lot causes risk violation",
    "reconciliation unknown",
    "STALE_MARKET_DATA",
    "SYMBOL_IDENTITY_INVALID",
    "RECONCILIATION_REQUIRED",
    "below_min_lot",
    "SAFETY_BLOCKED",
    "stale heartbeat:oms",
    "stale heartbeat:gateway",
    "stale heartbeat:mt5",
)


@pytest.mark.parametrize("reason", _ADVISORY)
def test_advisory_does_not_halt(reason: str) -> None:
    assert classify_halt_condition(reason) is HaltClass.ADVISORY
    assert does_not_halt_new_entry(reason) is True
    assert halts_new_entry(reason) is False


@pytest.mark.parametrize("reason", _HARD)
def test_hard_block_halts(reason: str) -> None:
    assert classify_halt_condition(reason) is HaltClass.HARD_BLOCK
    assert halts_new_entry(reason) is True
    assert does_not_halt_new_entry(reason) is False


def test_empty_reason_is_unclassified() -> None:
    assert classify_halt_condition("") is HaltClass.UNCLASSIFIED
    assert does_not_halt_new_entry("") is False
    assert halts_new_entry("") is False


def test_stale_quote_is_not_confused_with_telemetry_stale() -> None:
    assert classify_halt_condition("stale quote") is HaltClass.HARD_BLOCK
    assert classify_halt_condition("UI/telemetry stale") is HaltClass.ADVISORY


def test_stale_quote_firewall_is_hard_block() -> None:
    verdict = evaluate_market_data_firewall(
        symbol="XAUUSD_I",
        bid=1.0,
        ask=1.1,
        quote_age_seconds=999.0,
        max_tick_age_seconds=120.0,
    )
    assert verdict.allow_new_entry is False
    assert verdict.first_blocking_gate == "STALE_MARKET_DATA"
    assert halts_new_entry(str(verdict.first_blocking_gate)) is True


def test_invalid_symbol_firewall_is_hard_block() -> None:
    verdict = evaluate_market_data_firewall(
        symbol="",
        bid=1.0,
        ask=1.1,
        quote_age_seconds=0.1,
        symbol_valid=False,
    )
    assert verdict.allow_new_entry is False
    assert verdict.first_blocking_gate == "SYMBOL_IDENTITY_INVALID"
    assert halts_new_entry(str(verdict.first_blocking_gate)) is True


def test_reconciliation_unknown_is_hard_block() -> None:
    gate = OrderAmbiguityGate()
    rec = gate.mark_unknown(
        decision_hash="h",
        symbol="XAUUSD_I",
        side="BUY",
        reason="reconciliation unknown",
    )
    assert rec.state in {
        AmbiguityState.UNKNOWN,
        AmbiguityState.RECONCILIATION_REQUIRED,
    }
    assert gate.has_blocking_ambiguity() is True
    assert halts_new_entry(rec.state.value) is True
    assert halts_new_entry("reconciliation unknown") is True


def test_continuous_ops_pauses_hard_blocks_not_advisory_heartbeats() -> None:
    from app.domain.institutional_trading.phase_a.plane import (
        reset_phase_a_plane_for_tests,
    )

    reset_phase_a_plane_for_tests()
    ctrl = ContinuousOperationController()
    quote = {
        "symbol": "XAUUSD_I",
        "bid": 2000.0,
        "ask": 2000.2,
        "quote_age_seconds": 1.0,
        "symbol_valid": True,
        "candles_ok": True,
        "market_open": True,
    }
    hard = ctrl.evaluate_new_entry_pause(
        gateway_available=False,
        mt5_connected=False,
        missing_heartbeats=("gateway", "mt5", "oms"),
        **quote,
    )
    assert hard.pause_new_entries is True
    for reason in hard.reasons:
        assert classify_halt_condition(reason) is HaltClass.HARD_BLOCK

    advisory = ctrl.evaluate_new_entry_pause(
        missing_heartbeats=("execution", "decision", "pme"),
        **quote,
    )
    assert advisory.pause_new_entries is False
    assert advisory.reasons == ()


def test_enrichment_exception_does_not_raise() -> None:
    from app.application.services.auto_trading_status import _enrich_from_adapter

    class BoomCollector:
        mt5_adapter = None
        settings = SimpleNamespace(mt5_gateway_base_url="")

        @property
        def last_health_payload(self) -> dict[str, object]:
            raise RuntimeError("optional enrichment boom")

    out = _enrich_from_adapter(BoomCollector())  # type: ignore[arg-type]
    assert out["account_trading_enabled"] is None
    assert out["market_data_live"] is None
    assert does_not_halt_new_entry("optional enrichment unavailable") is True
