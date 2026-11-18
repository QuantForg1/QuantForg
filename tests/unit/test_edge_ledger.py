"""Edge Ledger: bucket statistics, evidence verdicts, journal row parsing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.application.services import edge_ledger as service
from app.domain.institutional_trading.performance_lab.edge_ledger import (
    ClosedTrade,
    bucket_stats,
    build_edge_ledger,
    session_of,
    verdict,
)

MONDAY_09 = datetime(2026, 11, 16, 9, 15, tzinfo=UTC)


def _trade(pnl: str, *, side: str = "SELL", at: datetime = MONDAY_09) -> ClosedTrade:
    value = Decimal(pnl)
    return ClosedTrade(side=side, opened_at=at, pnl=value, r_multiple=value / 2)


@pytest.mark.unit
def test_bucket_stats_profit_factor_and_r() -> None:
    stats = bucket_stats([_trade("3"), _trade("-2"), _trade("1"), _trade("-1")])
    assert stats["trades"] == 4
    assert stats["win_rate_pct"] == "50.0"
    assert stats["net_usd"] == "1.00"
    assert stats["profit_factor"] == "1.33"
    assert stats["avg_win_r"] == "1.00"
    assert stats["avg_loss_r"] == "-0.75"
    assert stats["verdict"] == "insufficient_data"


@pytest.mark.unit
def test_verdict_needs_thirty_trades() -> None:
    assert verdict(29, Decimal("3")) == "insufficient_data"
    assert verdict(30, Decimal("1.10")) == "edge"
    assert verdict(30, Decimal("1.05")) == "marginal"
    assert verdict(30, Decimal("0.80")) == "no_edge"
    assert verdict(30, None) == "no_losses_yet"


@pytest.mark.unit
def test_sessions_follow_utc_liquidity_windows() -> None:
    assert session_of(4) == "asia"
    assert session_of(9) == "london"
    assert session_of(13) == "london_ny_overlap"
    assert session_of(18) == "new_york"
    assert session_of(22) == "late"


@pytest.mark.unit
def test_ledger_breakdowns_and_worst_first_findings() -> None:
    losers = [_trade("-1", side="BUY") for _ in range(12)]
    asia = MONDAY_09.replace(hour=4)
    winners = [_trade("2", at=asia + timedelta(days=1)) for _ in range(12)]
    report = build_edge_ledger(losers + winners)
    assert report["overall"]["trades"] == 24
    assert report["breakdowns"]["side"]["BUY"]["net_usd"] == "-12.00"
    assert report["breakdowns"]["session_utc"]["asia"]["net_usd"] == "24.00"
    assert report["breakdowns"]["weekday"]["Tue"]["trades"] == 12
    worst = report["findings_worst_first"][0]
    assert worst["net_usd"] == "-12.00"
    assert all(f["trades"] >= 10 for f in report["findings_worst_first"])


@pytest.mark.unit
def test_rows_to_trades_keeps_closed_gold_rows_in_utc() -> None:
    rows: list[dict[str, Any]] = [
        {
            "symbol": "XAUUSD",
            "side": "SELL",
            "status": "CLOSED",
            "opened_at": "2026-11-16T11:15:00+02:00",
            "pnl": "1.5",
            "r_multiple": "0.5",
        },
        {
            "symbol": "XAUUSD",
            "side": "BUY",
            "status": "OPEN",
            "opened_at": "2026-11-16T09:00:00Z",
            "pnl": None,
        },
        {
            "symbol": "EURUSD",
            "side": "BUY",
            "status": "CLOSED",
            "opened_at": "2026-11-16T09:00:00Z",
            "pnl": "1",
        },
    ]
    trades = service.rows_to_trades(rows, symbol_prefix="xau")
    assert len(trades) == 1
    assert trades[0].opened_at.hour == 9
    assert trades[0].pnl == Decimal("1.5")


@pytest.mark.unit
def test_report_is_unavailable_without_supabase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "_rest", lambda: None)
    report = service.build_edge_ledger_report(days=30)
    assert report["available"] is False


@pytest.mark.unit
def test_report_pages_through_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    pages: list[dict[str, str]] = []
    row = {
        "symbol": "XAUUSD",
        "side": "SELL",
        "status": "CLOSED",
        "opened_at": "2026-11-16T04:00:00Z",
        "pnl": "1",
        "r_multiple": "0.5",
    }

    class _Resp:
        def __init__(self, data: list[dict[str, Any]]) -> None:
            self._data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, Any]]:
            return self._data

    class _Client:
        def __init__(self, *a: Any, **k: Any) -> None:
            _ = a, k

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

        def get(self, url: str, *, headers: Any, params: dict[str, str]) -> _Resp:
            _ = url, headers
            pages.append(params)
            first = params["offset"] == "0"
            return _Resp([row] * (service._PAGE if first else 5))

    monkeypatch.setattr(service, "_rest", lambda: ("https://db.example/rest/v1", "k"))
    monkeypatch.setattr(httpx, "Client", _Client)
    report = service.build_edge_ledger_report()
    assert report["available"] is True
    assert report["overall"]["trades"] == service._PAGE + 5
    assert [p["offset"] for p in pages] == ["0", str(service._PAGE)]
    assert pages[0]["status"] == "eq.CLOSED"
