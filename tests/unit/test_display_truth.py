"""Displayed and gated values must match the order's own prices.

Owner screenshot 2026-10-21 ~19:27 UTC (/admin/live-trading, prod 37b5ce98):
XAUUSD SELL entry 4117.935, SL 4129.415, TP 4112.108, shown RR 1.27.
Price RR is 5.827 / 11.48 = 0.51 and the $11.48 SL breaks the $2 owner cap.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.live_trading_control import (
    LiveOrderRequest,
    LiveTradingRiskConfig,
    evaluate_signal_quality,
    price_reward_risk,
)
from app.domain.institutional_trading.owner_live_limits import evaluate_owner_entry

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ENTRY = Decimal("4117.9349999999995")
SL = Decimal("4129.415142854")
TP = Decimal("4112.108000004")


def test_price_rr_for_screenshot_signal() -> None:
    rr = price_reward_risk("SELL", ENTRY, SL, TP)
    assert rr is not None
    assert round(rr, 2) == Decimal("0.51")


@pytest.mark.parametrize(
    ("direction", "entry", "sl", "tp", "expected"),
    [
        ("BUY", "100", "98", "103", Decimal("1.5")),
        ("SELL", "100", "102", "97", Decimal("1.5")),
        ("BUY", "100", "102", "103", None),  # SL on the wrong side
        ("SELL", "100", "102", "101", None),  # TP on the wrong side
        ("WAIT", "100", "98", "103", None),
    ],
)
def test_price_rr_sides(
    direction: str, entry: str, sl: str, tp: str, expected: Decimal | None
) -> None:
    rr = price_reward_risk(direction, Decimal(entry), Decimal(sl), Decimal(tp))
    assert rr == expected


def test_model_rr_cannot_pass_the_rr_gate() -> None:
    req = LiveOrderRequest(
        symbol="XAUUSD",
        direction="SELL",
        price=ENTRY,
        entry=ENTRY,
        stop_loss=SL,
        take_profit=TP,
        score=Decimal("76"),
        regime="UNKNOWN",
        signal_status="TAKE",
        evidence={"WHY": "x"},
        reward_risk=Decimal("1.27"),  # model value from the screenshot
    )
    gates = {g.key: g for g in evaluate_signal_quality(req, LiveTradingRiskConfig())}
    assert gates["acceptable_rr"].passed is False
    assert gates["acceptable_rr"].reason == "reward_risk_below_minimum"


def test_owner_guard_rejects_screenshot_signal() -> None:
    reasons = evaluate_owner_entry(
        symbol="XAUUSD",
        side="SELL",
        volume=Decimal("0.01"),
        entry=ENTRY,
        stop_loss=SL,
        take_profit=TP,
        spread=Decimal("0.424"),
        contract_size=Decimal("100"),
        equity=Decimal("50.84"),
        commission=Decimal("0"),
    )
    joined = " ".join(reasons)
    # $11.48 at 0.01 lot (contract 100) is far above the $2.00 owner cap.
    assert "OWNER_SL_RISK" in joined


def test_signal_row_rr_comes_from_prices() -> None:
    from app.application.services.signal_center_service import (
        _row_from_research_opportunity,
    )

    row = _row_from_research_opportunity(
        {
            "symbol": "XAUUSD",
            "direction": "SELL",
            "opportunity_score": 76,
            "RR": 1.27,
            "entry_candidate": str(ENTRY),
            "SL_candidate": str(SL),
            "TP_candidate": str(TP),
        }
    )
    assert row["rr"] == pytest.approx(0.51)
    assert row["RR"] == pytest.approx(0.51)


def test_signal_row_keeps_model_rr_without_prices() -> None:
    from app.application.services.signal_center_service import (
        _row_from_research_opportunity,
    )

    row = _row_from_research_opportunity(
        {"symbol": "XAUUSD", "direction": "SELL", "opportunity_score": 76, "RR": 1.27}
    )
    assert row["rr"] == pytest.approx(1.27)


def test_cached_symbol_info_never_calls_gateway() -> None:
    from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

    client = GatewayMT5Client(base_url="https://gw.example", token="tok")
    assert client.cached_symbol_info("XAUUSD") is None


# --- Item 3: 30-minute tracker must follow broker positions -----------------


def _tracker(**kw: object) -> str:
    from app.domain.institutional_trading.operations.gold_execution_readiness import (
        resolve_tracker_state,
    )

    base: dict[str, object] = {
        "has_current_scan": True,
        "eligible_count": 1,
        "execution_ready": True,
        "current_focus": "XAUUSD",
        "next_action": "RISK_ASSESSMENT",
        "fault_class": None,
        "decision_state": "EXECUTION_READY",
        "named_reject": None,
        "window_active": True,
        "first_natural_trade": True,  # set by a forwarded (refused) order
    }
    base.update(kw)
    return resolve_tracker_state(**base)  # type: ignore[arg-type]


def test_tracker_not_position_open_with_zero_broker_positions() -> None:
    assert _tracker(broker_open_positions=0) != "POSITION_OPEN"


def test_tracker_position_open_when_broker_holds_one() -> None:
    assert _tracker(broker_open_positions=1) == "POSITION_OPEN"


def test_tracker_unknown_broker_count_keeps_previous_behaviour() -> None:
    assert _tracker(broker_open_positions=None) == "POSITION_OPEN"


# --- Item 4: diagnostics outcome is the real result -------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "cycle_outcome": "forwarded",
                "forwarded_to_oms": True,
                "executed": False,
                "abort_reason": "EXECUTION_DISABLED",
                "primary_rejection": None,
            },
            "not_filled: EXECUTION_DISABLED",
        ),
        (
            {
                "cycle_outcome": "forwarded",
                "forwarded_to_oms": True,
                "executed": False,
                "abort_reason": None,
                "primary_rejection": None,
            },
            "not_filled: no broker ticket",
        ),
        (
            {
                "cycle_outcome": "forwarded",
                "forwarded_to_oms": True,
                "executed": True,
                "abort_reason": None,
                "primary_rejection": None,
            },
            "filled",
        ),
        (
            {
                "cycle_outcome": "no_trade",
                "forwarded_to_oms": False,
                "executed": False,
                "abort_reason": None,
                "primary_rejection": "MTF_MISALIGNMENT",
            },
            "rejected: MTF_MISALIGNMENT",
        ),
        (
            {
                "cycle_outcome": "no_trade",
                "forwarded_to_oms": False,
                "executed": False,
                "abort_reason": None,
                "primary_rejection": None,
            },
            "no_trade",
        ),
    ],
)
def test_cycle_result(kwargs: dict[str, object], expected: str) -> None:
    from app.application.services.strategy_diagnostics import resolve_cycle_result

    assert resolve_cycle_result(**kwargs) == expected  # type: ignore[arg-type]
