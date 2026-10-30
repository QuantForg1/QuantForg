"""Shadow mode (owner 2026-10-24): live checks, paper outcome, never an order."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services import institutional_execution_engine as iee
from app.application.services.operator_alerts import shadow_bars_utc
from app.domain.institutional_trading import shadow_book as sb

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

T0 = datetime(2026, 10, 26, 10, 0, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(tmp_path / "ops_state.json"))
    sb.reset_shadow_book_for_tests()


def _sell(book: sb.ShadowBook, **kw) -> sb.ShadowTrade:
    args = {
        "symbol": "XAUUSD_I",
        "side": "SELL",
        "volume": D("0.01"),
        "entry": D("4000.000"),
        "stop_loss": D("4002.000"),
        "take_profit": D("3996.000"),
        "bid": D("4000.000"),
        "ask": D("4000.200"),
        "equity": D("32.88"),
        "now": T0,
    }
    args.update(kw)
    return book.record_entry(**args)


def _bar(minute: int, hi: str, lo: str, sp: str = "0.200"):
    return (T0.replace(second=0) + timedelta(minutes=minute), D(hi), D(lo), D(sp))


# ---------------------------------------------------------------- book
def test_default_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANTFORG_SHADOW_MODE", raising=False)
    assert sb.shadow_mode_enabled() is False
    monkeypatch.setenv("QUANTFORG_SHADOW_MODE", "true")
    assert sb.shadow_mode_enabled() is True


def test_sell_closes_at_tp_using_the_ask() -> None:
    book = sb.ShadowBook()
    t = _sell(book)
    assert t.planned_risk_usd == D("2.200")  # (2.000 + 0.200) x 100 x 0.01
    # Bid low 3995.9 + spread 0.2 = ask 3996.1: TP 3996.0 not reached yet.
    assert book.update(bars=[_bar(1, "4000.5", "3995.9")]) is None
    closed = book.update(bars=[_bar(2, "3999.0", "3995.7")])
    assert closed is t and t.outcome == "TP"
    assert t.pnl_usd == D("4.00") and t.r_multiple == D("1.82")


def test_sl_is_checked_before_tp_and_entry_bar_is_ignored() -> None:
    book = sb.ShadowBook()
    t = _sell(book)
    # The entry minute's own range happened before the entry: ignored.
    assert book.update(bars=[_bar(0, "4005.0", "3990.0")]) is None
    closed = book.update(bars=[_bar(1, "4001.9", "3995.0")])  # ask high 4002.1
    assert closed is t and t.outcome == "SL" and t.pnl_usd == D("-2.00")


def test_tick_closes_between_bars() -> None:
    book = sb.ShadowBook()
    t = _sell(book)
    closed = book.update(bars=[], bid=D("3995.700"), ask=D("3995.900"), now=T0)
    assert closed is t and t.outcome == "TP"


def test_one_shadow_position_at_a_time() -> None:
    book = sb.ShadowBook()
    _sell(book)
    assert "SHADOW_POSITION_OPEN" in book.entry_block_reason(equity=D("32.88"), now=T0)


def test_nine_percent_cap_uses_shadow_equity() -> None:
    book = sb.ShadowBook()
    t = _sell(book)
    book.update(bars=[_bar(1, "4002.5", "3999.0")])  # SL: -2.00
    assert t.outcome == "SL"
    # Shadow equity 30.88 -> 9% = 2.77: a 2.80 planned risk is refused.
    reason = book.entry_block_reason(
        equity=D("32.88"), now=T0, planned_risk_usd=D("2.80")
    )
    assert reason and reason.startswith("SHADOW_SL_RISK")
    assert (
        book.entry_block_reason(equity=D("32.88"), now=T0, planned_risk_usd=D("2.70"))
        is None
    )


def test_daily_stop_on_shadow_pnl() -> None:
    book = sb.ShadowBook()
    for k in range(5):  # 5 x -2.00 = -10.00 > 25% of day-start 32.88 (8.22)
        t = _sell(book, now=T0 + timedelta(minutes=10 * k))
        book.update(bars=[_bar(10 * k + 1, "4002.5", "3999.0")])
        assert t.outcome == "SL"
    reason = book.entry_block_reason(equity=D("32.88"), now=T0 + timedelta(hours=1))
    assert reason and reason.startswith("SHADOW_DAILY_STOP")
    # Next UTC day: the daily stop no longer applies.
    assert (
        book.entry_block_reason(equity=D("32.88"), now=T0 + timedelta(days=1)) is None
    )


def test_persistence_round_trip() -> None:
    book = sb.ShadowBook()
    t = _sell(book)
    book.update(bars=[_bar(1, "3999.0", "3995.0")])
    copy = sb.ShadowBook()
    copy.hydrate(book.to_payload())
    assert len(copy.trades) == 1
    assert copy.trades[0].outcome == t.outcome == "TP"
    assert copy.trades[0].pnl_usd == t.pnl_usd


def test_bar_times_are_converted_from_server_time() -> None:
    now = datetime(2026, 10, 26, 10, 0, 40, tzinfo=UTC)
    rates = [
        SimpleNamespace(
            open_time=datetime(2026, 10, 26, h, m),  # server time = UTC+2
            high=D("1"),
            low=D("1"),
            spread_points=200,
        )
        for h, m in ((11, 58), (11, 59), (12, 0))
    ]
    bars = shadow_bars_utc(rates, now=now)
    assert [b[0].strftime("%H:%M") for b in bars] == ["09:58", "09:59", "10:00"]
    assert bars[0][3] == D("0.200")


# ---------------------------------------------------------------- run_submit
def _submit(monkeypatch: pytest.MonkeyPatch):
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, client = _engine()
    sent: list = []
    original = client.order_send

    def order_send(request):
        sent.append(request)
        return original(request)

    monkeypatch.setattr(client, "order_send", order_send)
    intent = iee.parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.30",
    )
    pipeline, _ = engine.run_submit(
        user_id=uuid4(),
        request_id=f"shadow-{uuid4().hex[:6]}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    return pipeline, sent, client


def test_shadow_mode_records_and_never_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTFORG_SHADOW_MODE", "true")
    pipeline, sent, client = _submit(monkeypatch)
    assert sent == [] and client._positions == []
    assert "SHADOW_MODE: recorded" in pipeline.message
    book = sb.get_shadow_book()
    t = book.open_trade()
    assert t is not None and t.side == "BUY" and t.entry == D("2320.80")
    assert t.stop_loss == D("2319.00") and t.take_profit == D("2324.30")
    # A second entry while the shadow position is open: refused, nothing sent.
    pipeline2, sent2, _ = _submit(monkeypatch)
    assert sent2 == [] and "SHADOW_POSITION_OPEN" in pipeline2.message
    assert len(book.trades) == 1


def test_owner_checks_still_apply_in_shadow_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFORG_SHADOW_MODE", "true")
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, _client = _engine()
    intent = iee.parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2321.50",  # RR far below 1.50
    )
    pipeline, _ = engine.run_submit(
        user_id=uuid4(),
        request_id="shadow-rr",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == "rejected"
    assert "SHADOW_MODE" not in pipeline.message
    assert sb.get_shadow_book().trades == []


def test_shadow_mode_off_sends_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from tests.unit.test_institutional_execution_engine import _allow_broker_submit

    monkeypatch.delenv("QUANTFORG_SHADOW_MODE", raising=False)
    _allow_broker_submit()
    _pipeline, sent, _ = _submit(monkeypatch)
    reset_live_trading_controller_for_tests()
    assert len(sent) == 1
    assert sb.get_shadow_book().trades == []
