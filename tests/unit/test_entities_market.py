"""Unit tests for market domain entities (Symbol, Order, Position, Trade, Signal)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.order import Order
from app.domain.entities.position import Position
from app.domain.entities.signal import Signal
from app.domain.entities.symbol import Symbol
from app.domain.entities.trade import Trade
from app.domain.enums.order import OrderSide, OrderStatus, OrderType
from app.domain.enums.position import PositionSide, PositionStatus
from app.domain.enums.signal import SignalDirection, SignalStatus
from app.domain.enums.symbol import SymbolStatus
from app.domain.exceptions.base import ConflictError, ValidationError
from app.domain.value_objects.money import Money


@pytest.mark.unit
class TestSymbol:
    def test_create_and_suspend(self) -> None:
        symbol = Symbol.create(
            code="EURUSD",
            name="Euro vs US Dollar",
            base_currency="EUR",
            quote_currency="USD",
        )
        assert symbol.is_tradable
        symbol.suspend()
        assert symbol.status == SymbolStatus.SUSPENDED
        symbol.activate()
        symbol.delist()
        assert symbol.status == SymbolStatus.DELISTED

    def test_same_currency_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Symbol.create(
                code="EUREUR",
                name="Invalid",
                base_currency="EUR",
                quote_currency="EUR",
            )


@pytest.mark.unit
class TestOrder:
    def test_market_order_fill(self) -> None:
        order = Order.create(
            trading_account_id=uuid4(),
            symbol_id=uuid4(),
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity="1.0",
        )
        order.accept()
        order.record_fill(fill_quantity="0.4", fill_price="1.1000")
        assert order.status == OrderStatus.PARTIALLY_FILLED
        order.record_fill(fill_quantity="0.6", fill_price="1.1001")
        assert order.status == OrderStatus.FILLED
        assert not order.is_open

    def test_limit_requires_price(self) -> None:
        with pytest.raises(ValidationError):
            Order.create(
                trading_account_id=uuid4(),
                symbol_id=uuid4(),
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity="1",
            )

    def test_cancel(self) -> None:
        order = Order.create(
            trading_account_id=uuid4(),
            symbol_id=uuid4(),
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity="1",
        )
        order.cancel()
        assert order.status == OrderStatus.CANCELLED
        with pytest.raises(ConflictError):
            order.accept()


@pytest.mark.unit
class TestPosition:
    def test_open_reduce_close(self) -> None:
        position = Position.open(
            trading_account_id=uuid4(),
            symbol_id=uuid4(),
            side=PositionSide.LONG,
            quantity="2.0",
            open_price="1.1000",
        )
        position.reduce(quantity="0.5", close_price="1.1010")
        assert position.status == PositionStatus.PARTIALLY_CLOSED
        assert str(position.quantity) == "1.5"
        position.close(close_price="1.1020")
        assert position.status == PositionStatus.CLOSED


@pytest.mark.unit
class TestTrade:
    def test_immutable(self) -> None:
        trade = Trade.record(
            trading_account_id=uuid4(),
            symbol_id=uuid4(),
            side=OrderSide.BUY,
            quantity="1",
            price="1.25",
            commission=Money.of("0.10", "USD"),
        )
        with pytest.raises(ConflictError):
            trade.touch()


@pytest.mark.unit
class TestSignal:
    def test_lifecycle(self) -> None:
        expires = datetime.now(UTC) + timedelta(hours=1)
        signal = Signal.create(
            symbol_id=uuid4(),
            direction=SignalDirection.BUY,
            confidence="0.7",
            expires_at=expires,
        )
        signal.activate()
        assert signal.status == SignalStatus.ACTIVE
        signal.consume()
        assert signal.status == SignalStatus.CONSUMED
        assert signal.consumed_at is not None
