"""Breakeven / trailing SL moves on an open position (owner, 2026-10-23).

Live 2026-10-23: every breakeven SL move was refused before order_send.
``run_submit`` judged it like a new entry ("open positions 1 at max 1",
sizing / remaining planned risk), and SL/TP moves were validated against the
opening-side price ("Sell take profit must be below entry price" while
bid <= TP < ask). Robot closes are out of scope here (owner decision).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_engine import (
    parse_order_intent,
)
from app.application.services.institutional_oms_manage_adapter import (
    InstitutionalOmsManageAdapter,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = pytest.mark.unit


def _sell_position(**kw) -> MT5Position:
    base = {
        "ticket": 777,
        "symbol": "XAUUSD",
        "side": "sell",
        "volume": D("0.01"),
        "open_price": D("2325.00"),
        "current_price": D("2320.80"),
        "stop_loss": D("2328.00"),
        "take_profit": D("2318.00"),
        "magic": 260720,
        "comment": "ite:v1:H:abc",
    }
    base.update(kw)
    return MT5Position(**base)


def _harness():
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, client = _engine()
    client._positions = [_sell_position()]
    sent: list = []
    original = client.order_send

    def order_send(request):
        sent.append(request)
        return original(request)

    client.order_send = order_send
    return InstitutionalOmsManageAdapter(engine=engine), client, sent


def _common() -> dict:
    return {
        "user_id": uuid4(),
        "request_id": "pme_777",
        "symbol": "XAUUSD",
        "position": 777,
        "connected": True,
        "login": 1,
    }


def test_breakeven_sl_move_reaches_the_broker() -> None:
    port, _client, sent = _harness()
    res = port.modify_sltp(
        side="sell",
        stop_loss=D("2324.10"),
        take_profit=D("2318.00"),
        comment="ite:v1:break_even:777",
        current_stop_loss=D("2328.00"),
        **_common(),
    )
    assert res.outcome == "success", res.message
    assert len(sent) == 1
    assert sent[0].oms_kind == "sltp"
    assert sent[0].stop_loss == D("2324.10")
    assert sent[0].take_profit == D("2318.00")


def test_sl_move_that_widens_risk_is_refused() -> None:
    port, _client, sent = _harness()
    res = port.modify_sltp(
        side="sell",
        stop_loss=D("2329.00"),
        take_profit=D("2318.00"),
        comment="ite:v1:trail:777",
        **_common(),
    )
    assert res.outcome == "rejected"
    assert "MANAGE_SL_WIDENS" in res.message
    assert sent == []


def test_manage_on_a_position_that_is_not_open_is_refused() -> None:
    port, client, sent = _harness()
    client._positions = []
    res = port.modify_sltp(
        side="sell",
        stop_loss=D("2324.10"),
        take_profit=D("2318.00"),
        comment="ite:v1:break_even:777",
        **_common(),
    )
    assert res.outcome == "rejected"
    assert "MANAGE_POSITION_NOT_OPEN" in res.message
    assert sent == []


def _check(**kw) -> list[str]:
    args = {
        "side": "SELL",
        "position_ticket": 777,
        "stop_loss": D("2324.10"),
        "take_profit": D("2318.00"),
        "positions": [_sell_position()],
    }
    args.update(kw)
    return ol.sltp_move_violations(**args)


def test_sltp_move_guard_rules() -> None:
    assert _check() == []
    assert _check(stop_loss=D("2328.00")) == []  # unchanged SL is fine
    assert any("OWNER_SL_REQUIRED" in r for r in _check(stop_loss=None))
    assert any("OWNER_TP_REQUIRED" in r for r in _check(take_profit=None))
    assert any("MANAGE_SIDE" in r for r in _check(side="BUY"))


def test_buy_sl_may_only_move_up() -> None:
    buy = _sell_position(
        side="buy",
        open_price=D("2316.00"),
        stop_loss=D("2313.00"),
        take_profit=D("2323.00"),
    )
    kw = {"side": "BUY", "take_profit": D("2323.00"), "positions": [buy]}
    assert _check(stop_loss=D("2316.90"), **kw) == []
    assert any("MANAGE_SL_WIDENS" in r for r in _check(stop_loss=D("2312.00"), **kw))


def test_sl_move_is_validated_against_the_closing_price() -> None:
    """10:01:09Z trade 7: SELL, TP 4021.693, bid 4021.600 / ask 4021.964.

    A SELL closes at the ask. TP below the ask is still valid at the broker,
    so the breakeven SL move must not be refused because bid <= TP.
    """
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, client = _engine()
    validation = engine.order_validation
    tick = client.latest_tick("XAUUSD")
    client.latest_tick = lambda _s: replace(tick, bid=D("4021.600"), ask=D("4021.964"))
    constraints = replace(validation.constraints_for("XAUUSD"), stops_level=0)

    def sltp(stop_loss: str):
        return parse_order_intent(
            symbol="XAUUSD",
            side="sell",
            order_type="market",
            volume="0.01",
            stop_loss=stop_loss,
            take_profit="4021.693",
            position=662581954,
            oms_kind="sltp",
        )

    ok, msg = validation.validate_stops(
        sltp("4028.62"), constraints, entry_price=D("0")
    )
    assert ok, msg
    # SL inside the spread (above bid, below ask) is invalid at the broker.
    ok, msg = validation.validate_stops(
        sltp("4021.800"), constraints, entry_price=D("0")
    )
    assert not ok
    assert "stop loss" in msg.lower()
