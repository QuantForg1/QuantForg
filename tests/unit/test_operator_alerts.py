"""Private operator alerts: broker-truth watcher, journal, summaries."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
from typing import Any

import pytest

from app.application.services import operator_alerts as oa

pytestmark = [pytest.mark.unit]

T0 = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class _Adapter:
    def __init__(self) -> None:
        self.up = True
        self.connected = True
        self.positions: list[Any] = []
        self.deals: list[Any] = []
        self.equity = D("50")

    def health(self) -> Any:
        if not self.up:
            raise ConnectionError("tunnel 530")
        return SimpleNamespace(connected=self.connected)

    def account_info(self) -> Any:
        if not self.up:
            raise ConnectionError("tunnel 530")
        return SimpleNamespace(equity=self.equity, balance=self.equity)

    def list_positions(self) -> list[Any]:
        return list(self.positions)

    def latest_tick(self, symbol: str) -> Any:
        return SimpleNamespace(bid=D("4100.00"), ask=D("4100.30"))

    def history_deals(self, *, date_from: datetime, date_to: datetime) -> list[Any]:
        return list(self.deals)


def _pos(**kw: Any) -> Any:
    base = {
        "ticket": 101,
        "symbol": "XAUUSD",
        "side": "sell",
        "volume": D("0.01"),
        "open_price": D("4100.00"),
        "stop_loss": D("4103.00"),
        "take_profit": D("4094.00"),
        "opened_at": T0,
    }
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch) -> tuple[oa.OperatorWatch, _Adapter, _Clock]:
    monkeypatch.setattr(oa, "_persist_alert", lambda *_a: None)
    monkeypatch.setattr(
        "app.application.services.ops_state_persistence.save_ops_state",
        lambda *_a: None,
    )
    clock = _Clock()
    adapter = _Adapter()
    alerter = oa.OperatorAlerter(
        oa.OperatorTelegramSender(token=None, chat_id=None), clock=clock
    )
    watch = oa.OperatorWatch(
        adapter=adapter,
        alerter=alerter,
        journal=oa.TradeJournal(rest=None),
        clock=clock,
        now_utc=lambda: T0,
    )
    return watch, adapter, clock


def _kinds(watch: oa.OperatorWatch) -> list[str]:
    return [k for k, _ in watch.alerter.history]


def test_gateway_offline_alerts_after_two_minutes_then_recovers(setup: Any) -> None:
    watch, adapter, clock = setup
    adapter.up = False
    watch.tick()
    clock.t += 119
    watch.tick()
    assert "GATEWAY OFFLINE" not in _kinds(watch)
    clock.t += 2
    watch.tick()
    clock.t += 60
    watch.tick()
    assert _kinds(watch).count("GATEWAY OFFLINE") == 1
    adapter.up = True
    watch.tick()
    assert "GATEWAY RECOVERED" in _kinds(watch)


def test_mt5_disconnect_alerts_only_after_two_minutes(setup: Any) -> None:
    watch, adapter, clock = setup
    adapter.connected = False
    watch.tick()
    clock.t += 121
    watch.tick()
    assert _kinds(watch).count("MT5 OFFLINE") == 1


def test_open_and_close_are_journaled_with_pnl_and_r(setup: Any) -> None:
    watch, adapter, clock = setup
    adapter.positions = [_pos()]
    watch.tick()
    opened = [m for k, m in watch.alerter.history if k == "ORDER OPENED"]
    assert len(opened) == 1
    # planned risk (3.00 + 0.30 spread) x 100 x 0.01 = 3.30 = 6.60% of 50
    assert "Planned risk $3.30 (6.60% of equity)" in opened[0]
    assert watch.journal.entries[101].status == "OPEN"

    adapter.positions = []
    adapter.deals = [
        SimpleNamespace(
            position_id=101,
            deal_type="entry_out",
            profit=D("6.00"),
            commission=D("-0.07"),
            swap=D("0"),
            price=D("4094.00"),
            time=T0 + timedelta(minutes=20),
        )
    ]
    clock.t += 30
    watch.tick()
    closed = [m for k, m in watch.alerter.history if k == "ORDER CLOSED"]
    assert len(closed) == 1
    entry = watch.journal.entries[101]
    assert entry.status == "CLOSED"
    assert entry.pnl == D("5.93")
    assert entry.r_multiple == D("1.80")  # 5.93 / 3.30
    assert "P/L +$5.93 (1.80R)" in closed[0]


def test_unknown_commission_does_not_publish_an_r_multiple(setup: Any) -> None:
    watch, adapter, clock = setup
    adapter.positions = [_pos()]
    watch.tick()
    adapter.positions = []
    adapter.deals = [
        SimpleNamespace(
            position_id=101,
            deal_type="entry_out",
            profit=D("6.00"),
            commission=None,
            swap=D("0"),
            price=D("1"),
            time=T0 + timedelta(minutes=20),
        )
    ]
    clock.t += 30
    watch.tick()
    entry = watch.journal.entries[101]
    assert entry.status == "CLOSED"
    assert entry.r_multiple is None
    assert entry.pnl == D("6.00")
    closed = [m for k, m in watch.alerter.history if k == "ORDER CLOSED"]
    assert len(closed) == 1
    assert "commission unknown" in closed[0]
    assert "1.80R" not in closed[0]


def test_close_waits_until_broker_history_shows_the_exit(setup: Any) -> None:
    watch, adapter, _clock = setup
    adapter.positions = [_pos()]
    watch.tick()
    adapter.positions = []
    watch.tick()  # no exit deal visible yet
    assert watch.journal.entries[101].status == "OPEN"
    assert "ORDER CLOSED" not in _kinds(watch)


@pytest.mark.parametrize(
    ("override", "needle"),
    [
        ({"symbol": "EURUSD"}, "non-Gold"),
        ({"volume": D("0.02")}, "volume 0.02"),
        ({"stop_loss": D("0")}, "missing stop loss"),
        ({"take_profit": D("0")}, "missing take profit"),
        ({"stop_loss": D("4110.00")}, "20.0% cap"),  # (10.00 + 0.30) = $10.30 > $10.00
    ],
)
def test_rule_violations_alert_with_pause_instruction(
    setup: Any, override: dict[str, Any], needle: str
) -> None:
    watch, adapter, _clock = setup
    adapter.positions = [_pos(**override)]
    watch.tick()
    violations = [m for k, m in watch.alerter.history if k == "RULE VIOLATION"]
    assert any(needle in m for m in violations)
    assert all("Press Pause on /admin/live-trading" in m for m in violations)


def test_compliant_position_has_no_violation(setup: Any) -> None:
    watch, adapter, _clock = setup
    adapter.positions = [_pos()]
    watch.tick()
    assert "RULE VIOLATION" not in _kinds(watch)


def test_equity_30pct_below_reference_alerts_once_per_day(setup: Any) -> None:
    watch, adapter, clock = setup
    adapter.equity = D("35")  # 30% below the $50 reference
    watch.tick()
    clock.t += 30
    watch.tick()
    assert _kinds(watch).count("EQUITY ALERT") == 1


def test_daily_summary_once_after_1715_utc(setup: Any) -> None:
    watch, _adapter, clock = setup
    watch.now_utc = lambda: T0.replace(hour=17, minute=14)
    watch.tick()
    assert "DAILY SUMMARY" not in _kinds(watch)
    watch.now_utc = lambda: T0.replace(hour=17, minute=15)
    watch.tick()
    clock.t += 30
    watch.tick()
    assert _kinds(watch).count("DAILY SUMMARY") == 1


def test_weekly_summary_on_friday(setup: Any) -> None:
    watch, _adapter, _clock = setup
    friday = datetime(2026, 10, 23, 17, 25, tzinfo=UTC)
    assert friday.weekday() == 4
    watch.now_utc = lambda: friday
    watch.tick()
    assert _kinds(watch).count("WEEKLY SUMMARY") == 1


def test_summarize_win_rate_avg_r_and_drawdown() -> None:
    def e(pnl: str, r: str) -> oa.JournalEntry:
        return oa.JournalEntry(
            ticket=1,
            symbol="XAUUSD",
            side="SELL",
            volume=D("0.01"),
            entry_price=D("1"),
            stop_loss=D("1"),
            take_profit=D("1"),
            spread=None,
            planned_risk_usd=D("3"),
            equity_at_open=D("50"),
            opened_at=T0,
            status="CLOSED",
            pnl=D(pnl),
            r_multiple=D(r),
        )

    stats = oa.summarize(
        [e("4.50", "1.5"), e("-3.00", "-1"), e("-3.00", "-1"), e("6.00", "2")]
    )
    assert stats["trades"] == 4
    assert stats["win_rate"] == D("50.0")
    assert stats["avg_r"] == D("0.38")
    assert stats["pnl"] == D("4.50")
    assert stats["max_dd"] == D("6.00")


def test_alerter_dedupes_by_key_and_throttles() -> None:
    clock = _Clock()
    alerter = oa.OperatorAlerter(
        oa.OperatorTelegramSender(token=None, chat_id=None), clock=clock
    )
    assert alerter.alert("X", "a", key="k") is True
    assert alerter.alert("X", "a", key="k") is False
    assert alerter.alert("Y", "b", key="t", throttle_s=60) is True
    clock.t += 61
    assert alerter.alert("Y", "b", key="t", throttle_s=60) is True


def test_repeated_errors_alert_at_five_within_ten_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oa, "_persist_alert", lambda *_a: None)
    alerter = oa.OperatorAlerter(oa.OperatorTelegramSender(token=None, chat_id=None))
    handler = oa.RepeatedErrorHandler(alerter)
    for _ in range(5):
        handler.emit(
            logging.LogRecord(
                "x", logging.ERROR, __file__, 1, {"event": "boom"}, None, None
            )
        )
    assert [k for k, _ in alerter.history] == ["REPEATED ERROR"]


@pytest.mark.asyncio
async def test_sender_posts_only_to_operator_chat() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def post(url: str, payload: dict[str, Any]) -> Any:
        calls.append((url, payload))
        return SimpleNamespace(status_code=200)

    sender = oa.OperatorTelegramSender(token="T0K", chat_id="12345", post=post)
    sender.enqueue("hello")
    await sender.drain()
    assert calls == [
        (
            "https://api.telegram.org/botT0K/sendMessage",
            {"chat_id": "12345", "text": "hello", "disable_web_page_preview": True},
        )
    ]


@pytest.mark.asyncio
async def test_unconfigured_sender_sends_nothing() -> None:
    sender = oa.OperatorTelegramSender(token="T0K", chat_id="", post=None)
    sender.enqueue("hello")
    await sender.drain()  # must not raise or call Telegram
    assert not sender.configured
