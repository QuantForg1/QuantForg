"""Small-account checks at the broker minimum. Stops and lots stay put."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.operations.small_account_feasibility import (
    OBSERVED_CONTRACT_SIZE,
    OBSERVED_SLIPPAGE,
    OBSERVED_SPREAD,
    OBSERVED_STOP_DISTANCE,
    OBSERVED_VOLUME_MIN,
    SMALL_ACCOUNT_EQUITIES,
    evaluate_min_volume,
    observed_min_lot_rows,
    risk_cap_usd,
)
from app.domain.institutional_trading.owner_live_limits import evaluate_owner_entry

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_unknown_commission_rejects_every_small_equity() -> None:
    rows = observed_min_lot_rows()
    assert [row.equity for row in rows] == list(SMALL_ACCOUNT_EQUITIES)
    for row in rows:
        assert row.accepted is False
        assert row.reason == "OWNER_COMMISSION_UNKNOWN"
        assert row.planned_risk_usd is None
        assert row.minimum_equity_usd is None
        assert row.volume == OBSERVED_VOLUME_MIN
        assert row.stop_distance == OBSERVED_STOP_DISTANCE
        # Arithmetic only. A zero-commission figure is not a certification.
        assert row.uncertified_zero_commission_equity_usd == Decimal("24.05")


def test_known_zero_commission_uses_the_twenty_percent_cap() -> None:
    rows = observed_min_lot_rows(commission=Decimal("0"))
    for row in rows:
        assert row.planned_risk_usd == Decimal("4.81")
        assert row.risk_cap_usd == risk_cap_usd(row.equity, Decimal("20"))
        assert row.minimum_equity_usd == Decimal("24.05")
        assert row.stop_distance == OBSERVED_STOP_DISTANCE
        assert row.volume == Decimal("0.01")
        if row.equity < Decimal("24.05"):
            assert row.accepted is False
            assert row.reason == "OWNER_SL_RISK"
            assert row.planned_risk_usd > row.risk_cap_usd
        else:
            assert row.accepted is True
            assert row.planned_risk_usd <= row.risk_cap_usd


def test_thirty_dollars_at_fourteen_percent_caps_at_four_twenty() -> None:
    assert risk_cap_usd(Decimal("30"), Decimal("14")) == Decimal("4.20")
    assert risk_cap_usd(Decimal("30.53"), Decimal("14")) == Decimal("4.27")
    assert risk_cap_usd(Decimal("30"), Decimal("20")) == Decimal("6.00")
    assert risk_cap_usd(Decimal("30.53"), Decimal("20")) == Decimal("6.10")
    assert Decimal("4.81") <= Decimal("6.10")


def test_wider_stop_is_not_shrunk_and_lot_is_not_raised() -> None:
    wide = evaluate_min_volume(
        equity=Decimal("30"),
        stop_distance=Decimal("10"),
        spread=OBSERVED_SPREAD,
        slippage=OBSERVED_SLIPPAGE,
        commission=Decimal("0"),
        volume=OBSERVED_VOLUME_MIN,
    )
    assert wide.accepted is False
    assert wide.reason == "OWNER_SL_RISK"
    assert wide.stop_distance == Decimal("10")
    assert wide.volume == Decimal("0.01")
    assert wide.planned_risk_usd is not None
    assert wide.planned_risk_usd > wide.risk_cap_usd
    above_cap = evaluate_min_volume(
        equity=Decimal("30"),
        stop_distance=OBSERVED_STOP_DISTANCE,
        spread=OBSERVED_SPREAD,
        slippage=OBSERVED_SLIPPAGE,
        commission=Decimal("0"),
        volume=Decimal("0.02"),
        max_lot=Decimal("0.01"),
    )
    assert above_cap.accepted is False
    assert above_cap.reason == "BROKER_VOLUME_ABOVE_LOT_CAP"
    assert above_cap.volume == Decimal("0.02")


def test_owner_entry_rejects_the_same_over_cap_geometry() -> None:
    entry = Decimal("3927.727")
    stop = entry - OBSERVED_STOP_DISTANCE
    take_profit = entry + (OBSERVED_STOP_DISTANCE * Decimal("2"))
    common = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": OBSERVED_VOLUME_MIN,
        "entry": entry,
        "stop_loss": stop,
        "take_profit": take_profit,
        "spread": OBSERVED_SPREAD,
        "contract_size": OBSERVED_CONTRACT_SIZE,
        "equity": Decimal("20"),
        "slippage": OBSERVED_SLIPPAGE,
    }
    unknown = evaluate_owner_entry(**common, commission=None)
    assert any(item.startswith("OWNER_COMMISSION_UNKNOWN") for item in unknown)
    known = evaluate_owner_entry(**common, commission=Decimal("0"))
    assert any(item.startswith("OWNER_SL_RISK") for item in known)


def test_equity_that_covers_the_zero_commission_risk_can_pass() -> None:
    covered = evaluate_min_volume(
        equity=Decimal("24.05"),
        stop_distance=OBSERVED_STOP_DISTANCE,
        spread=OBSERVED_SPREAD,
        slippage=OBSERVED_SLIPPAGE,
        commission=Decimal("0"),
    )
    assert covered.accepted is True
    assert covered.planned_risk_usd == Decimal("4.81")
    assert covered.risk_cap_usd >= covered.planned_risk_usd
    short = evaluate_min_volume(
        equity=Decimal("24.04"),
        stop_distance=OBSERVED_STOP_DISTANCE,
        spread=OBSERVED_SPREAD,
        slippage=OBSERVED_SLIPPAGE,
        commission=Decimal("0"),
    )
    assert short.accepted is False
    assert short.reason == "OWNER_SL_RISK"
