"""Shared entry decision. No broker and no order port."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.unified_decision import (
    NormalizedSignal,
    resolve_unified,
    signal_from_decision,
    signal_from_m1_note,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _signal(
    source: str,
    direction: str,
    stop: Decimal | None,
    *,
    confidence: Decimal | None = None,
    holding_period: str = "",
    counts_without_stop: bool = False,
) -> NormalizedSignal:
    return NormalizedSignal(
        source=source,
        direction=direction,
        confidence=confidence,
        timeframe=source,
        invalidation=stop,
        holding_period=holding_period,
        direction_counts_without_stop=counts_without_stop,
    )


def test_no_signal_waits() -> None:
    plan = resolve_unified(None, None, primary_executable=True)
    assert plan.action == "wait"
    assert plan.reason == "no_actionable_signal"
    assert plan.submit_primary is False
    assert plan.submit_m1 is False
    assert plan.sources == ()


def test_primary_only_keeps_one_order() -> None:
    primary = _signal(
        "primary",
        "BUY",
        Decimal("2300"),
        confidence=Decimal("80"),
        holding_period="intraday",
    )
    plan = resolve_unified(primary, None, primary_executable=True)
    assert plan.action == "buy"
    assert plan.reason == "primary_only"
    assert plan.owner == "primary"
    assert plan.submit_primary is True
    assert plan.submit_m1 is False
    assert plan.confidence == Decimal("80")
    assert plan.invalidation == Decimal("2300")
    assert plan.holding_period == "intraday"


def test_m1_only_when_primary_is_not_a_side() -> None:
    m1 = _signal(
        "m1",
        "sell",
        Decimal("2310"),
        confidence=Decimal("10"),
        holding_period="m1",
    )
    primary = _signal("primary", "NO_TRADE", None, confidence=Decimal("90"))
    plan = resolve_unified(primary, m1, primary_executable=False)
    assert plan.action == "sell"
    assert plan.reason == "m1_only"
    assert plan.owner == "m1"
    assert plan.submit_primary is False
    assert plan.submit_m1 is True
    assert plan.confidence == Decimal("10")
    assert plan.sources == ("m1",)


def test_same_direction_does_not_sum_confidence_or_duplicate() -> None:
    primary = _signal("primary", "buy", Decimal("2300"), confidence=Decimal("40"))
    m1 = _signal("m1", "buy", Decimal("2301"), confidence=Decimal("50"))
    owned = resolve_unified(primary, m1, primary_executable=True)
    assert owned.action == "buy"
    assert owned.reason == "primary_owns_order"
    assert owned.submit_primary is True
    assert owned.submit_m1 is False
    assert owned.confidence == Decimal("40")
    assert owned.sources == ("primary", "m1")
    handed = resolve_unified(primary, m1, primary_executable=False)
    assert handed.reason == "m1_same_direction_after_primary_block"
    assert handed.submit_primary is False
    assert handed.submit_m1 is True
    assert handed.confidence == Decimal("50")
    assert handed.owner == "m1"


def test_opposite_directions_wait_without_a_tie_break() -> None:
    primary = _signal("primary", "buy", Decimal("2300"), confidence=Decimal("1"))
    m1 = _signal("m1", "sell", Decimal("2310"), confidence=Decimal("99"))
    up = resolve_unified(
        primary,
        m1,
        primary_executable=True,
        higher_timeframe_bias="up",
    )
    down = resolve_unified(
        primary,
        m1,
        primary_executable=False,
        higher_timeframe_bias="down",
    )
    assert up == down
    assert up.action == "wait"
    assert up.reason == "direction_conflict"
    assert up.submit_primary is False
    assert up.submit_m1 is False
    assert up.confidence is None
    assert up.owner == ""


def test_missing_m1_stop_does_not_block_or_submit() -> None:
    primary = _signal("primary", "sell", Decimal("2310"), confidence=Decimal("70"))
    m1 = _signal("m1", "buy", None, confidence=Decimal("90"))
    plan = resolve_unified(primary, m1, primary_executable=True)
    assert plan.reason == "primary_only"
    assert plan.submit_primary is True
    assert plan.submit_m1 is False


def test_primary_intent_without_a_stop_still_conflicts() -> None:
    primary = _signal(
        "primary",
        "SELL",
        None,
        counts_without_stop=True,
    )
    m1 = _signal("m1", "buy", Decimal("2300"))
    plan = resolve_unified(primary, m1, primary_executable=True)
    assert plan.reason == "direction_conflict"
    assert plan.submit_primary is False
    assert plan.submit_m1 is False


def test_blocked_primary_can_leave_the_same_direction_to_m1() -> None:
    primary = _signal("primary", "buy", None, counts_without_stop=True)
    m1 = _signal("m1", "BUY", Decimal("2290"), confidence=Decimal("15"))
    plan = resolve_unified(primary, m1, primary_executable=False)
    assert plan.reason == "m1_same_direction_after_primary_block"
    assert plan.submit_primary is False
    assert plan.submit_m1 is True
    assert plan.confidence == Decimal("15")
    assert plan.invalidation == Decimal("2290")


def test_m1_note_without_a_valid_entry_is_not_a_signal() -> None:
    note = signal_from_m1_note(
        {
            "action": "sell",
            "reason": "combined_planned_risk_above_9_percent",
            "stop": "2300",
            "entry_valid": False,
        }
    )
    primary = signal_from_decision(
        SimpleNamespace(
            action=SimpleNamespace(value="BUY"),
            stop_zone=SimpleNamespace(mid=Decimal("2290"), low=Decimal("2288")),
            confidence=80,
            expected_duration="intraday",
        )
    )
    plan = resolve_unified(primary, note, primary_executable=True)
    assert plan.reason == "primary_only"
    assert plan.submit_m1 is False
    assert primary.invalidation == Decimal("2290")
    assert primary.holding_period == "intraday"
    assert primary.direction_counts_without_stop is True


def test_wrong_side_stop_note_is_not_actionable() -> None:
    note = signal_from_m1_note(
        {
            "action": "buy",
            "reason": "stop_wrong_side",
            "stop": "2400",
            "entry_valid": False,
        }
    )
    assert note.invalidation is None
    plan = resolve_unified(None, note, primary_executable=False)
    assert plan.reason == "no_actionable_signal"
    assert plan.submit_m1 is False
