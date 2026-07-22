"""Unit tests — Integration Sprint V1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.integration_sprint_v1 import IntegrationSprintV1
from app.domain.integration_sprint_v1.config import MISSING, IntegrationSprintConfig
from app.domain.integration_sprint_v1.durable_store import DurableResearchStore
from app.domain.integration_sprint_v1.feeds import IntegrationFeeds
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class _FakeDeal:
    ticket: int
    profit: Decimal
    comment: str = "test"


@dataclass
class _FakePos:
    ticket: int
    symbol: str
    volume: Decimal


@dataclass
class _FakeTick:
    bid: Decimal
    ask: Decimal
    time: datetime


@dataclass
class _FakeAccount:
    login: int
    balance: Decimal


class _FakeMT5:
    def history_deals(self, *, date_from=None, date_to=None):
        _ = date_from, date_to
        return [_FakeDeal(1, Decimal("12.5")), _FakeDeal(2, Decimal("-4"))]

    def list_positions(self):
        return [_FakePos(10, GOLD_SYMBOL, Decimal("0.1"))]

    def latest_tick(self, symbol: str):
        _ = symbol
        return _FakeTick(Decimal("2350"), Decimal("2350.3"), datetime.now(UTC))

    def account_info(self):
        return _FakeAccount(12345, Decimal("10000"))

    def health(self):
        return {"connected": True, "ok": True}

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        _ = symbol, timeframe, start_pos, count
        return [{"time": "t", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]


class _FakeCalendar:
    def list_events(self, *, limit: int = 20, as_of=None):
        _ = limit, as_of
        from app.domain.interfaces.news import EconomicEvent

        return [
            EconomicEvent(
                id="1",
                title="CPI",
                country="USD",
                impact="high",
                scheduled_at="2026-07-22T12:00:00Z",
                actual="",
                forecast="3.0",
                previous="3.1",
            )
        ]


class _FakeJournal:
    def all_recent(self, *, limit: int = 200):
        return [
            {
                "journal_id": "j1",
                "latency_ms": 40,
                "execution_result": "filled",
            }
        ][:limit]


def test_hard_locks() -> None:
    status = IntegrationSprintV1().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["invent_market_data"] is False
    assert status["capabilities"]["never_modify_execution_pipeline"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = IntegrationSprintConfig().update(
        {
            "allow_order_send": True,
            "allow_modify_risk_engine": True,
            "invent_trades": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_modify_risk_engine is False
    assert cfg.invent_trades is False


def test_missing_without_adapters() -> None:
    feeds = IntegrationFeeds(IntegrationSprintConfig())
    trade = feeds.mt5_trade_feed()
    assert trade.available is False
    assert trade.missing_reason == MISSING
    bus = feeds.unified_data_bus()
    assert "mt5_trade_feed" in bus["missing_feeds"]
    assert bus["read_only"] is True


def test_connected_feeds_and_hydrate() -> None:
    feeds = IntegrationFeeds(
        IntegrationSprintConfig(),
        mt5_adapter=_FakeMT5(),
        execution_journal=_FakeJournal(),
        economic_calendar=_FakeCalendar(),
        durable_store=DurableResearchStore(),
    )
    system = IntegrationSprintV1(
        config=IntegrationSprintConfig(), feeds=feeds
    )
    bus = system.bus_snapshot()
    assert "mt5_trade_feed" in bus["connected_feeds"]
    assert "mt5_position_feed" in bus["connected_feeds"]
    assert "broker_account_feed" in bus["connected_feeds"]
    assert "economic_calendar_provider" in bus["connected_feeds"]
    assert bus["health_summary"]["healthy"] >= 4

    ivp = system.hydrate("ivp")
    assert ivp["status"] == "available"
    assert len(ivp["evaluate_body"]["completed_trades"]) == 2

    rmip = system.hydrate("rmip")
    events = rmip["evaluate_body"]["economic_events"]
    assert events[0]["actual"] is None  # never invent empty actual
    assert events[0]["forecast"] == "3.0"

    store = system.storage_append(
        "ivp", {"payload": {"score": 1}, "source": "test"}
    )
    assert store["status"] == "available"
    listed = system.storage_list("ivp")
    assert listed["items"][0]["append_only"] is True


def test_no_order_send_in_domain() -> None:
    from pathlib import Path

    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "integration_sprint_v1"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
