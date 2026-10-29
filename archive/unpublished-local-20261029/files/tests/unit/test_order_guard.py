"""Gateway order guard. Never calls MetaTrader5."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.mt5_order import OrderIntent, TradeRequest
from app.domain.enums.order import OrderSide, OrderType
from app.domain.value_objects.mt5_order import LotSize
from services.mt5_gateway.order_guard import (
    RETCODE_ORDER_GUARD_REJECTED,
    ClientOrderIdRegistry,
    OrderGuardRejected,
    enforce_order_guard,
)


def _quote() -> dict[str, object]:
    return {
        "bid": "2320.00",
        "ask": "2320.30",
        "specs": {
            "contract_size": "100",
            "tick_size": "0.01",
            "tick_value": "1",
        },
    }


def _entry(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "symbol": "XAUUSD_i",
        "action": "buy",
        "volume": 0.01,
        "sl": 2310.00,
        "tp": 2340.00,
        "client_order_id": "entry-1",
    }
    body.update(overrides)
    return body


def _guard(body: dict[str, object], **kwargs: object) -> str:
    registry = kwargs.pop("registry", None)
    if not isinstance(registry, ClientOrderIdRegistry):
        registry = ClientOrderIdRegistry()
    return enforce_order_guard(
        body,
        registry=registry,
        equity=kwargs.pop("equity", Decimal("1000")),
        quote=kwargs.pop("quote", _quote()),
        positions_lookup=kwargs.pop("positions_lookup", lambda: []),
    )


def _rejects(body: dict[str, object], code: str, **kwargs: object) -> None:
    with pytest.raises(OrderGuardRejected) as caught:
        _guard(body, **kwargs)
    assert caught.value.code == code
    assert caught.value.retcode == RETCODE_ORDER_GUARD_REJECTED


@pytest.mark.unit
def test_xaujpy_entry_is_rejected() -> None:
    _rejects(_entry(symbol="XAUJPY"), "GUARD_GOLD_ONLY")


@pytest.mark.unit
def test_position_ticket_without_close_kind_is_not_a_close() -> None:
    _rejects(
        _entry(position=123, sl=0, volume=1.0, symbol="EURUSD"),
        "GUARD_ENTRY_POSITION",
    )


@pytest.mark.unit
def test_missing_client_order_id_is_rejected() -> None:
    _rejects(_entry(client_order_id=""), "GUARD_CLIENT_ORDER_ID_REQUIRED")


@pytest.mark.unit
def test_duplicate_client_order_id_is_rejected() -> None:
    registry = ClientOrderIdRegistry()
    assert _guard(_entry(), registry=registry) == "entry"
    _rejects(_entry(), "GUARD_DUPLICATE_CLIENT_ORDER_ID", registry=registry)


@pytest.mark.unit
def test_wrong_side_buy_stop_is_rejected() -> None:
    _rejects(_entry(sl=2321.00), "GUARD_SL_WRONG_SIDE")


@pytest.mark.unit
def test_wrong_side_sell_stop_is_rejected() -> None:
    _rejects(_entry(action="sell", sl=2319.00), "GUARD_SL_WRONG_SIDE")


@pytest.mark.unit
def test_non_positive_volume_is_rejected() -> None:
    _rejects(_entry(volume=0), "GUARD_VOLUME")
    _rejects(_entry(volume=-0.01), "GUARD_VOLUME")


@pytest.mark.unit
def test_missing_quote_or_equity_fails_closed() -> None:
    _rejects(_entry(), "GUARD_EQUITY_UNAVAILABLE", equity=None)
    _rejects(_entry(), "GUARD_QUOTE_UNAVAILABLE", quote=None)
    _rejects(_entry(), "GUARD_QUOTE_UNAVAILABLE", quote={"bid": "0", "ask": "2320"})


@pytest.mark.unit
def test_planned_risk_above_nine_percent_is_rejected_and_exact_is_allowed() -> None:
    # 0.01 lot * 90.00 distance / 0.01 tick * $1 = $90.00 = 9% of $1000.
    assert _guard(_entry(sl=2230.30)) == "entry"
    _rejects(_entry(sl=2230.29, client_order_id="over-9"), "GUARD_MAX_RISK")


@pytest.mark.unit
def test_close_requires_ticket_symbol_and_volume_not_above_position() -> None:
    rows = [{"ticket": 7, "symbol": "XAUUSD_i", "volume": "0.02", "type": 0}]

    def lookup() -> list[dict[str, object]]:
        return rows

    _rejects(
        {"symbol": "XAUUSD_i", "oms_kind": "close", "volume": 0.01},
        "GUARD_CLOSE_TICKET_REQUIRED",
        positions_lookup=lookup,
    )
    _rejects(
        {
            "symbol": "XAUUSD_i",
            "oms_kind": "close",
            "position": 7,
            "volume": 0.03,
        },
        "GUARD_CLOSE_VOLUME",
        positions_lookup=lookup,
    )
    _rejects(
        {
            "symbol": "XAUJPY",
            "oms_kind": "close",
            "position": 7,
            "volume": 0.01,
        },
        "GUARD_GOLD_ONLY",
        positions_lookup=lookup,
    )
    assert (
        _guard(
            {
                "symbol": "XAUUSD_i",
                "oms_kind": "partial_close",
                "position": 7,
                "volume": 0.02,
            },
            positions_lookup=lookup,
        )
        == "close"
    )


@pytest.mark.unit
def test_sltp_rejects_wrong_side_stop() -> None:
    rows = [
        {
            "ticket": 4,
            "symbol": "XAUUSD_i",
            "volume": "0.01",
            "type": 0,
            "sl": "2310",
        }
    ]

    def lookup() -> list[dict[str, object]]:
        return rows

    _rejects(
        {
            "symbol": "XAUUSD_i",
            "oms_kind": "sltp",
            "position": 4,
            "sl": 2321,
            "tp": 2340,
        },
        "GUARD_SL_WRONG_SIDE",
        positions_lookup=lookup,
    )


@pytest.mark.unit
def test_trade_request_carries_client_order_id() -> None:
    request = TradeRequest(
        symbol="XAUUSD_i",
        action="buy",
        volume=Decimal("0.01"),
        price=Decimal("2320.30"),
        stop_loss=Decimal("2310"),
        take_profit=Decimal("2340"),
        deviation=20,
        magic=0,
        client_order_id="cid-64",
    )
    assert request.to_dict()["client_order_id"] == "cid-64"
    intent = OrderIntent(
        symbol="XAUUSD_i",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
        client_order_id="  cid-64  ",
    )
    assert intent.client_order_id == "cid-64"
    assert intent.to_dict()["client_order_id"] == "cid-64"
