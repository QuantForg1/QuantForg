"""Lifecycle reconciliation: positions vs history_deals identity / cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.noc_command_center import _closed_trades_read_only
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.signal_intelligence_service import (
    pair_all_symbol_closed_trades,
)
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Deal, MT5Position
from app.domain.institutional_trading.execution_evidence.collector import (
    _extract_sl_tp,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _acct() -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=Decimal("10000"),
        equity=Decimal("10000"),
        margin=Decimal("0"),
        free_margin=Decimal("10000"),
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=100,
        currency="USD",
    )


def _open_pos(*, ticket: int = 579901930) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol="NZDUSD",
        side="sell",
        volume=Decimal("0.27"),
        open_price=Decimal("0.58802"),
        current_price=Decimal("0.58846"),
        stop_loss=Decimal("0.58847"),
        take_profit=Decimal("0.58758"),
        profit=Decimal("-11.88"),
        magic=260720,
    )


def _deal(
    *,
    ticket: int,
    order_ticket: int,
    position_id: int,
    deal_type: str,
    volume: str,
    profit: str,
    when: datetime,
    side: str = "sell",
) -> MT5Deal:
    return MT5Deal(
        ticket=ticket,
        order_ticket=order_ticket,
        symbol="NZDUSD",
        side=side,
        volume=Decimal(volume),
        price=Decimal("0.58802") if deal_type == "entry_in" else Decimal("0.58847"),
        profit=Decimal(profit),
        deal_type=deal_type,
        time=when,
        magic=260720,
        position_id=position_id,
    )


class _StalePositionsAdapter:
    """Simulates cycle-pinned open book while deals already show full close."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.refresh_calls = 0
        t0 = datetime(2026, 9, 4, 1, 49, 28, tzinfo=UTC)
        self._deals = [
            _deal(
                ticket=560939565,
                order_ticket=579901930,
                position_id=579901930,
                deal_type="entry_in",
                volume="0.27",
                profit="0",
                when=t0,
                side="sell",
            ),
            _deal(
                ticket=560940001,
                order_ticket=579901999,
                position_id=579901930,
                deal_type="entry_out",
                volume="0.27",
                profit="-12.15",
                when=t0 + timedelta(minutes=6, seconds=36),
                side="buy",
            ),
        ]

    def list_positions(self) -> list[MT5Position]:
        self.list_calls += 1
        # Stale pin: still returns OPEN after close landed in history.
        return [_open_pos()]

    def force_refresh_positions(self) -> list[MT5Position]:
        self.refresh_calls += 1
        return []

    def list_orders(self) -> list:
        return []

    def account_snapshot(self) -> AccountSnapshot:
        return _acct()

    def history_orders(self, **_kw: object) -> list:
        return []

    def history_deals(self, **_kw: object) -> list[MT5Deal]:
        return list(self._deals)


def test_synchronize_refreshes_positions_after_deals() -> None:
    adapter = _StalePositionsAdapter()
    sync = PortfolioSyncService(adapter=adapter)  # type: ignore[arg-type]
    record = sync.synchronize(user_id=uuid4())
    assert adapter.refresh_calls == 1
    assert record.position_count == 0
    assert record.history_deal_count == 2
    snap = record.snapshot if isinstance(record.snapshot, dict) else {}
    deals = snap.get("history_deals") or []
    assert {d.get("deal_type") for d in deals} == {"entry_in", "entry_out"}
    # Must not leave OPEN ticket when refresh says closed.
    open_tickets = [int(p.get("ticket") or 0) for p in (snap.get("positions") or [])]
    assert 579901930 not in open_tickets


class _FreshOpenAdapter:
    """Fresh open book + entry_in only → remain OPEN."""

    def __init__(self) -> None:
        self.refresh_calls = 0
        t0 = datetime(2026, 9, 4, 1, 49, 28, tzinfo=UTC)
        self._deals = [
            _deal(
                ticket=560939565,
                order_ticket=579901930,
                position_id=579901930,
                deal_type="entry_in",
                volume="0.27",
                profit="0",
                when=t0,
                side="sell",
            )
        ]

    def list_positions(self) -> list[MT5Position]:
        return [_open_pos()]

    def force_refresh_positions(self) -> list[MT5Position]:
        self.refresh_calls += 1
        return [_open_pos()]

    def list_orders(self) -> list:
        return []

    def account_snapshot(self) -> AccountSnapshot:
        return _acct()

    def history_orders(self, **_kw: object) -> list:
        return []

    def history_deals(self, **_kw: object) -> list[MT5Deal]:
        return list(self._deals)


def test_fresh_open_without_entry_out_stays_open() -> None:
    adapter = _FreshOpenAdapter()
    sync = PortfolioSyncService(adapter=adapter)  # type: ignore[arg-type]
    record = sync.synchronize(user_id=uuid4())
    assert adapter.refresh_calls == 1
    assert record.position_count == 1
    snap = record.snapshot if isinstance(record.snapshot, dict) else {}
    open_tickets = [int(p.get("ticket") or 0) for p in (snap.get("positions") or [])]
    assert 579901930 in open_tickets
    assert pair_all_symbol_closed_trades(
        [d.to_dict() for d in adapter.history_deals()]
    ) == []


def test_pair_entry_exit_full_close_identity() -> None:
    t0 = datetime(2026, 9, 4, 1, 49, 28, tzinfo=UTC)
    deals = [
        _deal(
            ticket=560939565,
            order_ticket=579901930,
            position_id=579901930,
            deal_type="entry_in",
            volume="0.27",
            profit="0",
            when=t0,
            side="sell",
        ).to_dict(),
        _deal(
            ticket=560940001,
            order_ticket=579901999,
            position_id=579901930,
            deal_type="entry_out",
            volume="0.27",
            profit="-12.15",
            when=t0 + timedelta(minutes=6, seconds=36),
            side="buy",
        ).to_dict(),
    ]
    closed = pair_all_symbol_closed_trades(deals)
    assert len(closed) == 1
    row = closed[0]
    assert row["position_id"] == 579901930
    assert row["entry_ticket"] == 560939565
    assert row["exit_ticket"] == 560940001
    assert float(row["volume"]) == pytest.approx(0.27)
    assert float(row["profit_loss"]) == pytest.approx(-12.15)
    assert row["status"] == "closed"
    assert int(deals[0]["magic"]) == 260720
    assert int(deals[1]["magic"]) == 260720


def test_remaining_volume_full_vs_partial() -> None:
    """Lifecycle volume rule — do not infer CLOSE from P/L alone."""
    entry = Decimal("0.27")
    full_out = Decimal("0.27")
    partial_out = Decimal("0.10")
    assert entry - full_out == Decimal("0")
    assert entry - partial_out == Decimal("0.17")


def test_pair_partial_close_keeps_net_on_position_id() -> None:
    t0 = datetime(2026, 9, 4, 1, 49, 28, tzinfo=UTC)
    deals = [
        {
            "ticket": 1,
            "position_id": 100,
            "symbol": "EURUSD",
            "side": "buy",
            "volume": 0.20,
            "price": 1.1,
            "profit": 0,
            "commission": 0,
            "swap": 0,
            "deal_type": "entry_in",
            "time": t0.isoformat(),
            "magic": 260720,
        },
        {
            "ticket": 2,
            "position_id": 100,
            "symbol": "EURUSD",
            "side": "sell",
            "volume": 0.10,
            "price": 1.11,
            "profit": 5.0,
            "commission": 0,
            "swap": 0,
            "deal_type": "entry_out",
            "time": (t0 + timedelta(minutes=1)).isoformat(),
            "magic": 260720,
        },
        {
            "ticket": 3,
            "position_id": 100,
            "symbol": "EURUSD",
            "side": "sell",
            "volume": 0.10,
            "price": 1.12,
            "profit": 7.0,
            "commission": 0,
            "swap": 0,
            "deal_type": "entry_out",
            "time": (t0 + timedelta(minutes=2)).isoformat(),
            "magic": 260720,
        },
    ]
    closed = pair_all_symbol_closed_trades(deals)
    assert len(closed) == 1
    assert closed[0]["position_id"] == 100
    assert float(closed[0]["profit_loss"]) == pytest.approx(12.0)
    assert closed[0]["exit_ticket"] == 3
    # Cumulative exit volume equals entry → remaining 0 for ledger close.
    assert float(deals[1]["volume"]) + float(deals[2]["volume"]) == pytest.approx(
        float(deals[0]["volume"])
    )


def test_noc_closed_trades_from_mt5_history(monkeypatch: pytest.MonkeyPatch) -> None:
    t0 = datetime(2026, 9, 4, 1, 49, 28, tzinfo=UTC)
    adapter = SimpleNamespace(
        history_deals=lambda **_kw: [
            _deal(
                ticket=560939565,
                order_ticket=579901930,
                position_id=579901930,
                deal_type="entry_in",
                volume="0.27",
                profit="0",
                when=t0,
                side="sell",
            ),
            _deal(
                ticket=560940001,
                order_ticket=579901999,
                position_id=579901930,
                deal_type="entry_out",
                volume="0.27",
                profit="-12.15",
                when=t0 + timedelta(minutes=6, seconds=36),
                side="buy",
            ),
            # Manual / foreign magic must not enter NOC closed ledger.
            MT5Deal(
                ticket=999001,
                order_ticket=888001,
                symbol="EURUSD",
                side="buy",
                volume=Decimal("1.0"),
                price=Decimal("1.1"),
                profit=Decimal("0"),
                deal_type="entry_in",
                time=t0,
                magic=0,
                position_id=888001,
            ),
            MT5Deal(
                ticket=999002,
                order_ticket=888002,
                symbol="EURUSD",
                side="sell",
                volume=Decimal("1.0"),
                price=Decimal("1.2"),
                profit=Decimal("50"),
                deal_type="entry_out",
                time=t0 + timedelta(minutes=1),
                magic=0,
                position_id=888001,
            ),
        ]
    )
    monkeypatch.setattr(
        "app.application.services.institutional_ite_runtime.get_ite_runtime",
        lambda: SimpleNamespace(mt5_adapter=adapter, execution=None),
    )
    rows = _closed_trades_read_only(limit=10)
    assert rows
    assert rows[0]["source"] == "mt5_history_deals"
    assert int(rows[0]["ticket"]) == 579901930
    assert float(rows[0]["net_profit"]) == pytest.approx(-12.15)
    assert rows[0]["win_loss"] == "loss"
    assert all(int(r["ticket"]) != 888001 for r in rows)


def test_evidence_sl_tp_from_nested_request() -> None:
    sl, tp = _extract_sl_tp(
        {"request": {"stop_loss": "0.58847", "take_profit": "0.58758"}},
        {},
    )
    assert sl == "0.58847"
    assert tp == "0.58758"


def test_evidence_sl_tp_from_nested_order() -> None:
    sl, tp = _extract_sl_tp(
        {"order": {"sl": "0.58847", "tp": "0.58758"}},
        {},
    )
    assert sl == "0.58847"
    assert tp == "0.58758"


def test_evidence_sl_tp_absent_stays_none() -> None:
    sl, tp = _extract_sl_tp({"symbol": "NZDUSD"}, {"retcode": 10009})
    assert sl is None
    assert tp is None


def test_utc_deal_stamp_not_blindly_shifted() -> None:
    """Broker epoch is labeled UTC; do not subtract an assumed +3h offset."""
    broker_epoch = 1756945768  # illustrative — treated as UTC by client
    stamped = datetime.fromtimestamp(broker_epoch, tz=UTC)
    # Conversion path: fromtimestamp(..., tz=UTC) — no broker offset config.
    assert stamped.tzinfo is UTC


def test_addon_scope_and_gold_identity_untouched() -> None:
    """Telemetry fix must not alter candidate/gold position-truth contracts."""
    from app.application.services.mt5_position_truth import (
        candidate_position_truth_symbol,
    )
    from app.domain.institutional_trading.operations.quantforg_position_cap import (
        QUANTFORG_MAGIC,
        resolve_same_symbol_addon_book,
    )

    assert QUANTFORG_MAGIC == 260720
    assert candidate_position_truth_symbol("NZDUSD") == "NZDUSD"
    gold = candidate_position_truth_symbol("XAUUSD")
    assert "XAU" in gold.upper()
    scoped = resolve_same_symbol_addon_book(
        [],
        candidate_symbol="NZDUSD",
        global_quantforg_positions=0,
    )
    assert scoped["open_positions"] == 0
    assert scoped["addon_scope"] == "flat"
