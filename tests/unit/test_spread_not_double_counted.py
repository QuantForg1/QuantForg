"""Planned risk measured from the fill price does not add the spread twice.

A BUY fills at the ask and its stop fills at the bid at the SL price; a SELL
fills at the bid and its stop fills at the ask. So |fill - SL| is already the
whole loss. The pre-trade gates used to add the spread on top of that
distance, rejecting entries that were inside the cap.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.risk_engine import RiskCheckInput, _risk_spread
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.order import OrderSide, OrderType
from app.domain.institutional_trading.owner_live_limits import max_planned_risk_usd
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.value_objects.mt5_order import LotSize, Slippage, StopLoss, TakeProfit
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


def _safety() -> tuple[ExecutionSafetyService, MT5Adapter]:
    client = MockMT5Client()
    client.known_commission = Decimal("0")
    adapter = MT5Adapter(client=client)
    adapter.initialize()
    adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
    validation = MT5OrderValidationService(adapter=adapter)
    return ExecutionSafetyService(adapter=adapter, order_validation=validation), adapter


def _decide(side: OrderSide, sl: Decimal, tp: Decimal):
    safety, _ = _safety()
    intent = OrderIntent(
        symbol="XAUUSD",
        side=side,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
        stop_loss=StopLoss.of(str(sl)),
        take_profit=TakeProfit.of(str(tp)),
        slippage=Slippage.of(0),
    )
    return safety.decide(
        user_id=uuid4(),
        request_id=f"spread-{side.value}-{sl}",
        intent=intent,
        connected=True,
        login=7,
        recent=[],
    )


def _quote() -> tuple[Decimal, Decimal, Decimal]:
    _, adapter = _safety()
    tick = adapter.latest_tick("XAUUSD")
    bid, ask = Decimal(str(tick.bid)), Decimal(str(tick.ask))
    equity = Decimal(str(adapter.account_info().equity))
    return bid, ask, equity


def _owner_sl(record) -> list[str]:
    return [r for r in record.rejection_reasons if r.startswith("OWNER_SL_RISK:")]


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
def test_stop_exactly_at_cap_passes_without_a_second_spread(side: OrderSide) -> None:
    bid, ask, equity = _quote()
    assert ask > bid  # a real spread exists; it must not be added again
    # 0.01 lot x 100 oz = $1 per 1.00 of price.
    distance = max_planned_risk_usd(equity)
    if side is OrderSide.BUY:
        sl, tp = ask - distance, ask + distance * 2
    else:
        sl, tp = bid + distance, bid - distance * 2
    record = _decide(side, sl, tp)
    assert _owner_sl(record) == []
    assert record.checks.get("owner_planned_risk") is not False


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
def test_stop_one_cent_beyond_cap_still_rejects(side: OrderSide) -> None:
    bid, ask, equity = _quote()
    distance = max_planned_risk_usd(equity) + Decimal("0.01")
    if side is OrderSide.BUY:
        sl, tp = ask - distance, ask + distance * 2
    else:
        sl, tp = bid + distance, bid - distance * 2
    record = _decide(side, sl, tp)
    assert record.checks.get("owner_planned_risk") is False
    assert len(_owner_sl(record)) == 1


def test_risk_engine_adds_spread_only_for_non_fill_distances() -> None:
    def check(*, from_fill: bool) -> RiskCheckInput:
        return RiskCheckInput(
            user_id=uuid4(),
            request_id="r",
            symbol="XAUUSD",
            side="buy",
            stop_loss_distance=Decimal("2.107"),
            spread=Decimal("0.394"),
            stop_measured_from_fill=from_fill,
        )

    assert _risk_spread(check(from_fill=False)) == Decimal("0.394")
    assert _risk_spread(check(from_fill=True)) == Decimal("0")
