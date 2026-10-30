"""Market entries must not go out with a stop that shrank since the signal.

Production 2026-10-23 07:31Z: SELL signal at 4019.155 with SL 4021.870 (stop
2.715 = 1.5 x M1 ATR). The order was sent 10 s later and filled at 4020.323,
so the real stop was 1.547 (43% narrower) and was hit 41 s later. The pre-send
checks used the signal price instead of the live bid.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _check(side: str, signal: str, live: str, sl: str) -> str | None:
    return ol.stop_shrink_violation(
        side=side, signal_price=D(signal), live_price=D(live), stop_loss=D(sl)
    )


def test_production_case_is_refused() -> None:
    reason = _check("SELL", "4019.155", "4020.323", "4021.870")
    assert reason is not None
    assert reason.startswith("OWNER_PRICE_DRIFT")
    assert "2.72 to 1.55" in reason


def test_ten_percent_boundary_sell() -> None:
    # planned 2.00; 10% shrink allowed -> live distance 1.80 ok, 1.79 refused
    assert _check("SELL", "100.00", "100.20", "102.00") is None
    assert _check("SELL", "100.00", "100.21", "102.00") is not None


def test_ten_percent_boundary_buy() -> None:
    assert _check("BUY", "100.00", "99.80", "98.00") is None
    assert _check("BUY", "100.00", "99.79", "98.00") is not None


def test_price_beyond_stop_is_refused() -> None:
    assert "beyond the stop loss" in (
        _check("SELL", "100.00", "102.10", "102.00") or ""
    )
    assert "beyond the stop loss" in (_check("BUY", "100.00", "97.90", "98.00") or "")


def test_favourable_drift_is_not_this_guards_concern() -> None:
    # Stop got wider: the 9% planned-risk and RR guards judge that case.
    assert _check("SELL", "100.00", "99.00", "102.00") is None
    assert _check("BUY", "100.00", "101.00", "98.00") is None


@pytest.mark.parametrize(
    ("signal", "live", "sl"),
    [
        (None, "100", "102"),
        ("100", None, "102"),
        ("100", "100", None),
        ("0", "100", "102"),
    ],
)
def test_unknown_inputs_defer_to_other_guards(
    signal: str | None, live: str | None, sl: str | None
) -> None:
    assert (
        ol.stop_shrink_violation(
            side="SELL",
            signal_price=D(signal) if signal else None,
            live_price=D(live) if live else None,
            stop_loss=D(sl) if sl else None,
        )
        is None
    )


def test_trade_3_compared_with_the_plan_price_is_refused() -> None:
    # Production 2026-10-23 08:23Z: the stop (SL 4021.417) was planned from the
    # scan mid 4018.285 (3.132 away); the order's own price was 4018.853 and
    # the fill 4018.633 (2.784 away, 11% narrower). Against the order price the
    # stop looks wider and slipped through; against the plan price it is refused.
    assert _check("SELL", "4018.853", "4018.633", "4021.417") is None
    reason = _check("SELL", "4018.285", "4018.633", "4021.417")
    assert reason is not None
    assert "3.13 to 2.78" in reason


def test_bridge_stamps_the_ai_plan_price_on_the_intent() -> None:
    from unittest.mock import MagicMock

    from app.domain.institutional_trading.decision_models import DecisionAction
    from app.domain.institutional_trading.execution.bridge import (
        ExecutionBridge,
        ExecutionBridgeConfig,
        ExecutionMode,
    )

    bridge = ExecutionBridge(
        oms=MagicMock(), config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
    )
    decision = MagicMock()
    decision.action = DecisionAction.SELL
    decision.stop_zone = MagicMock(low=D("4021.0"), high=D("4022.0"))
    decision.target_zone = MagicMock(low=D("4012.0"), high=D("4013.0"))
    decision.approved_lots = D("0.01")
    decision.symbol = "XAUUSD"
    decision.input_hash = "abcdefghijklmnop"
    decision.reasons = ()
    decision.ai_score = {
        "entry": "4018.285",
        "stop_loss": "4021.417",
        "take_profit": "4012.813",
    }
    context = MagicMock()
    context.account.mid_price = D("4018.700")
    context.account.atr = D("1.85")
    intent = bridge._build_intent(decision, context)
    assert intent.stop_loss is not None
    assert intent.stop_loss.value == D("4021.417")
    assert intent.plan_price == D("4018.285")
    assert intent.price is None  # market order: no broker price is sent


@pytest.mark.parametrize(
    ("plan_price", "refused"),
    [("2321.50", True), ("2320.90", False)],
)
def test_run_submit_refuses_a_stop_that_shrank_since_the_plan(
    plan_price: str, refused: bool
) -> None:
    """End to end: BUY at the mock ask 2320.80 with SL 2319.00 (1.80 live).

    Planned from 2321.50 the stop was 2.50 -> 28% narrower -> refused before
    order_send. Planned from 2320.90 it was 1.90 -> 5% narrower -> allowed.
    """
    from uuid import uuid4

    from app.application.services.institutional_execution_engine import (
        parse_order_intent,
    )
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, client = _engine()
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.30",
        plan_price=plan_price,
    )
    pipeline, decision = engine.run_submit(
        user_id=uuid4(),
        request_id=f"drift-{plan_price}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    text = str(pipeline)
    if refused:
        assert pipeline.outcome == "rejected"
        assert "OWNER_PRICE_DRIFT" in text
        assert client._positions == []
    else:
        assert "OWNER_PRICE_DRIFT" not in text
        assert "OWNER_MIN_RR" not in text
        assert decision.decision.value == "allow", pipeline
