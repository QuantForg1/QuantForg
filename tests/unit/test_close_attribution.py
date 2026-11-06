"""Broker-confirmed close attribution — analytics-only regression suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.services.close_attribution import (
    attribute_missing_tickets,
    find_broker_exit_for_position,
    reconcile_historical_closes,
    reconcile_pending_closes,
    record_broker_confirmed_close,
    reset_close_attribution_ledger_for_tests,
    strategy_id_from_entry_comment,
)
from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.ai_scalping.strategies.attribution_store import (
    StrategyAttributionStore,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    PositionLifecycleState,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _deal(
    *,
    ticket: int,
    position_id: int,
    deal_type: str,
    price: float,
    profit: float = 0.0,
    commission: float = 0.0,
    swap: float = 0.0,
    comment: str = "",
    volume: float = 0.01,
    side: str = "buy",
    minutes: int = 0,
    magic: int = QUANTFORG_MAGIC,
) -> dict:
    t0 = datetime(2026, 11, 4, 16, 0, tzinfo=UTC) + timedelta(minutes=minutes)
    return {
        "ticket": ticket,
        "order_ticket": position_id,
        "position_id": position_id,
        "symbol": "XAUUSD",
        "side": side,
        "volume": volume,
        "price": price,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "deal_type": deal_type,
        "time": t0.isoformat(),
        "magic": magic,
        "comment": comment,
    }


def _managed(ticket: int) -> ManagedPosition:
    return ManagedPosition(
        ticket=ticket,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("4042.000"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal("4040.000"),
        risk_distance=Decimal("2"),
        opened_at=datetime.now(UTC),
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("4040.000"),
        current_tp=Decimal("4044.000"),
        magic=QUANTFORG_MAGIC,
    )


class _Adapter:
    def __init__(
        self,
        rows: list[MT5Position] | None = None,
        *,
        deals: list[dict] | None = None,
        raise_on_positions: Exception | None = None,
        return_none: bool = False,
    ) -> None:
        self._rows = list(rows or [])
        self._deals = list(deals or [])
        self._raise = raise_on_positions
        self._return_none = return_none
        self._client = SimpleNamespace(
            invalidate_positions_cache=lambda: None,
            _positions_cache=None,
            _positions_cache_at=0.0,
        )

    def list_positions(self) -> list[MT5Position] | None:
        if self._raise is not None:
            raise self._raise
        if self._return_none:
            return None
        return list(self._rows)

    def history_deals(self, **_kwargs: object) -> list[dict]:
        return list(self._deals)


@pytest.fixture
def ledger(tmp_path: Path):
    return reset_close_attribution_ledger_for_tests(tmp_path / "ledger.json")


@pytest.fixture
def stats_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    book = StrategyStatsBook(_path=tmp_path / "stats.json")
    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.strategies.stats.get_strategy_stats_book",
        lambda: book,
    )
    return book


@pytest.fixture
def attr_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = StrategyAttributionStore(path=tmp_path / "attr.json")
    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.strategies.attribution_store.get_strategy_attribution_store",
        lambda: store,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.strategies.attribution_store._STORE",
        store,
    )
    return store


def test_strategy_id_from_entry_comment_engine_tags_only() -> None:
    assert strategy_id_from_entry_comment("m1:mom-sell-3903.523") == "m1_micro"
    # ite:* is engine-only — never invent ite_primary as a strategy_id.
    assert strategy_id_from_entry_comment("ite:v1:S:abc") is None
    assert strategy_id_from_entry_comment("[sl 3904.463]") is None
    assert strategy_id_from_entry_comment("momentum_scalping") is None


def test_entry_comment_attributes_when_store_empty(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Broker entry comment survives after SL overwrites the open comment."""
    pid = 679243921
    deals = [
        _deal(
            ticket=657036214,
            position_id=pid,
            deal_type="entry_in",
            price=3903.523,
            comment="m1:mom-sell-3903.523",
            minutes=0,
        ),
        _deal(
            ticket=657036300,
            position_id=pid,
            deal_type="entry_out",
            price=3904.897,
            profit=-1.37,
            comment="[sl 3904.463]",
            side="buy",
            minutes=1,
        ),
    ]
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: type("T", (), {"observe_close": staticmethod(lambda **_k: None)})(),
    )
    evidence = find_broker_exit_for_position(deals, position_id=pid)
    assert evidence is not None
    assert evidence.entry_comment.startswith("m1:")
    result = record_broker_confirmed_close(
        evidence=evidence, ledger=ledger, source="test_entry_comment"
    )
    assert result["strategy_id"] == "m1_micro"
    assert result["soe_recorded"] is True


def test_sl_closure_records_soe_once(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 683675942
    attr_store.bind_fill(
        strategy_id="trend_continuation",
        engine="soe",
        ticket=pid,
        position_id=pid,
    )
    deals = [
        _deal(
            ticket=661318398,
            position_id=pid,
            deal_type="entry_in",
            price=4042.747,
            comment="ite:v1:S:219753224df0",
            minutes=0,
        ),
        _deal(
            ticket=661321656,
            position_id=pid,
            deal_type="entry_out",
            price=4040.743,
            profit=-2.0,
            comment="[sl 4040.749]",
            side="sell",
            minutes=2,
        ),
    ]
    closes: list[dict] = []

    class _Tel:
        def observe_close(self, **kwargs: object) -> None:
            closes.append(dict(kwargs))

    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: _Tel(),
    )

    evidence = find_broker_exit_for_position(deals, position_id=pid)
    assert evidence is not None
    assert evidence.close_reason == "sl"
    assert evidence.net_pnl == pytest.approx(-2.0)
    assert evidence.exit_price == pytest.approx(4040.743)

    first = record_broker_confirmed_close(
        evidence=evidence, ledger=ledger, source="test_sl"
    )
    second = record_broker_confirmed_close(
        evidence=evidence, ledger=ledger, source="test_sl_dup"
    )
    assert first["status"] == "recorded"
    assert first["strategy_id"] == "trend_continuation"
    assert second["status"] == "duplicate"
    snap = stats_book.snapshot()["strategies"]
    row = next(r for r in snap if r["strategy_id"] == "trend_continuation")
    assert row["losses"] == 1
    assert row["wins"] == 0
    assert row["running_pnl"] == pytest.approx(-2.0)
    assert len(closes) == 1


def test_tp_closure_records_win(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 900001
    attr_store.bind_fill(
        strategy_id="momentum_scalping", engine="soe", ticket=pid, position_id=pid
    )
    deals = [
        _deal(
            ticket=1,
            position_id=pid,
            deal_type="entry_in",
            price=4000.0,
            comment="ite:v1:S:abc",
        ),
        _deal(
            ticket=2,
            position_id=pid,
            deal_type="entry_out",
            price=4003.0,
            profit=3.0,
            comment="[tp 4003.000]",
            side="sell",
            minutes=5,
        ),
    ]
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: SimpleNamespace(observe_close=lambda **_k: None),
    )
    evidence = find_broker_exit_for_position(deals, position_id=pid)
    assert evidence is not None
    assert evidence.close_reason == "tp"
    out = record_broker_confirmed_close(evidence=evidence, ledger=ledger)
    assert out["status"] == "recorded"
    row = next(
        r
        for r in stats_book.snapshot()["strategies"]
        if r["strategy_id"] == "momentum_scalping"
    )
    assert row["wins"] == 1
    assert row["running_pnl"] == pytest.approx(3.0)


def test_gateway_outage_does_not_drop_or_attribute(
    ledger, stats_book, attr_store
) -> None:
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(_managed(55))
    adapter = _Adapter(raise_on_positions=TimeoutError("gateway timeout"))
    account = AccountRiskState(
        equity=Decimal("22"),
        balance=Decimal("22"),
        free_margin=Decimal("20"),
        open_positions=1,
        already_in_trade=True,
    )
    sync = force_sync_positions(
        adapter, symbol="XAUUSD", internal_positions=1, position_engine=engine
    )
    assert sync.reliable is False
    assert sync.repaired is False
    assert 55 in engine._positions
    applied = apply_mt5_position_truth(account, sync)
    assert applied.open_positions == 1
    assert applied.already_in_trade is True
    assert stats_book.snapshot()["strategies"] == []


def test_incomplete_none_snapshot_does_not_false_close(ledger, stats_book) -> None:
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(_managed(77))
    adapter = _Adapter(return_none=True)
    sync = force_sync_positions(
        adapter, symbol="XAUUSD", internal_positions=1, position_engine=engine
    )
    assert sync.reliable is False
    assert 77 in engine._positions
    assert stats_book.snapshot()["strategies"] == []


def test_delayed_history_queues_pending_then_reconciles(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 683682967
    attr_store.bind_fill(
        strategy_id="trend_continuation", engine="soe", ticket=pid, position_id=pid
    )
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: SimpleNamespace(observe_close=lambda **_k: None),
    )
    # No deals yet → pending, no SOE row.
    pending = attribute_missing_tickets(tickets=[pid], deals=[], ledger=ledger)
    assert pending[0]["status"] == "pending_history"
    assert stats_book.snapshot()["strategies"] == []

    deals = [
        _deal(
            ticket=10,
            position_id=pid,
            deal_type="entry_in",
            price=4042.337,
            comment="ite:v1:S:0d3f844242a6",
        ),
        _deal(
            ticket=11,
            position_id=pid,
            deal_type="entry_out",
            price=4040.783,
            profit=-1.55,
            comment="[sl 4040.785]",
            side="sell",
            minutes=3,
        ),
    ]
    out = reconcile_pending_closes(deals=deals, ledger=ledger)
    assert any(r.get("status") == "recorded" for r in out)
    row = next(
        r
        for r in stats_book.snapshot()["strategies"]
        if r["strategy_id"] == "trend_continuation"
    )
    assert row["losses"] == 1
    assert row["running_pnl"] == pytest.approx(-1.55)


def test_duplicate_close_event_not_double_counted(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 4242
    attr_store.bind_fill(
        strategy_id="trend_continuation", engine="soe", ticket=pid, position_id=pid
    )
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: SimpleNamespace(observe_close=lambda **_k: None),
    )
    deals = [
        _deal(ticket=1, position_id=pid, deal_type="entry_in", price=100.0),
        _deal(
            ticket=2,
            position_id=pid,
            deal_type="entry_out",
            price=99.0,
            profit=-1.0,
            comment="[sl 99]",
            side="sell",
            minutes=1,
        ),
    ]
    r1 = attribute_missing_tickets(tickets=[pid], deals=deals, ledger=ledger)
    r2 = attribute_missing_tickets(tickets=[pid], deals=deals, ledger=ledger)
    assert r1[0]["status"] == "recorded"
    assert r2[0]["status"] == "duplicate"
    row = next(
        r
        for r in stats_book.snapshot()["strategies"]
        if r["strategy_id"] == "trend_continuation"
    )
    assert row["losses"] == 1


def test_partial_close_keeps_binding_until_flat(attr_store) -> None:
    attr_store.bind_fill(
        strategy_id="smc_scalping",
        engine="soe",
        ticket=12,
        position_id=12,
        volume=0.02,
    )
    attr_store.note_partial_close(ticket=12, position_id=12, closed_volume=0.01)
    assert attr_store.resolve(ticket=12) is not None
    assert attr_store.resolve(ticket=12).remaining_volume == pytest.approx(0.01)
    # Ticket still on MT5 book → attribute_missing_tickets not invoked.
    # Flat clears binding via fully_closed.
    attr_store.note_partial_close(
        ticket=12, position_id=12, closed_volume=0.01, fully_closed=True
    )
    assert attr_store.resolve(ticket=12) is None


def test_missing_strategy_still_records_telemetry_not_invented_sid(
    ledger, stats_book, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 555
    observed: list[dict] = []

    class _Tel:
        def observe_close(self, **kwargs: object) -> None:
            observed.append(dict(kwargs))

    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: _Tel(),
    )
    deals = [
        _deal(ticket=1, position_id=pid, deal_type="entry_in", price=10.0),
        _deal(
            ticket=2,
            position_id=pid,
            deal_type="entry_out",
            price=9.0,
            profit=-1.0,
            comment="[sl 9]",
            side="sell",
            minutes=1,
        ),
    ]
    evidence = find_broker_exit_for_position(deals, position_id=pid)
    assert evidence is not None
    out = record_broker_confirmed_close(evidence=evidence, ledger=ledger)
    assert out["strategy_id"] is None
    assert out["telemetry_recorded"] is True
    assert stats_book.snapshot()["strategies"] == []
    assert len(observed) == 1


def test_force_sync_attributes_sl_then_drops_pme(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 683675942
    attr_store.bind_fill(
        strategy_id="trend_continuation", engine="soe", ticket=pid, position_id=pid
    )
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: SimpleNamespace(observe_close=lambda **_k: None),
    )
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(_managed(pid))
    deals = [
        _deal(
            ticket=661318398,
            position_id=pid,
            deal_type="entry_in",
            price=4042.747,
            comment="ite:v1:S:219753224df0",
        ),
        _deal(
            ticket=661321656,
            position_id=pid,
            deal_type="entry_out",
            price=4040.743,
            profit=-2.0,
            comment="[sl 4040.749]",
            side="sell",
            minutes=2,
        ),
    ]
    adapter = _Adapter(rows=[], deals=deals)
    sync = force_sync_positions(
        adapter,
        symbol="XAUUSD",
        internal_positions=1,
        position_engine=engine,
        history_deals=deals,
    )
    assert sync.reliable is True
    assert sync.repaired is True
    assert pid not in engine._positions
    row = next(
        r
        for r in stats_book.snapshot()["strategies"]
        if r["strategy_id"] == "trend_continuation"
    )
    assert row["losses"] == 1
    assert row["running_pnl"] == pytest.approx(-2.0)


def test_historical_reconcile_identified_losers(
    ledger, stats_book, attr_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tickets 683675942 / 683682967 — broker history + fill-time strategy evidence."""
    monkeypatch.setattr(
        "app.application.services.strategy_performance_telemetry.get_strategy_performance_telemetry",
        lambda: SimpleNamespace(observe_close=lambda **_k: None),
    )
    deals = [
        _deal(
            ticket=661318398,
            position_id=683675942,
            deal_type="entry_in",
            price=4042.747,
            comment="ite:v1:S:219753224df0",
        ),
        _deal(
            ticket=661321656,
            position_id=683675942,
            deal_type="entry_out",
            price=4040.743,
            profit=-2.0,
            comment="[sl 4040.749]",
            side="sell",
            minutes=2,
        ),
        _deal(
            ticket=661324971,
            position_id=683682967,
            deal_type="entry_in",
            price=4042.337,
            comment="ite:v1:S:0d3f844242a6",
            minutes=10,
        ),
        _deal(
            ticket=661328000,
            position_id=683682967,
            deal_type="entry_out",
            price=4040.783,
            profit=-1.55,
            comment="[sl 4040.785]",
            side="sell",
            minutes=13,
        ),
    ]
    # Bindings restored from fill lifecycle evidence — not invented exits.
    results = reconcile_historical_closes(
        position_ids=[683675942, 683682967],
        deals=deals,
        strategy_bindings={
            683675942: "trend_continuation",
            683682967: "trend_continuation",
        },
        ledger=ledger,
    )
    assert all(r["status"] == "recorded" for r in results)
    assert sum(float(r["net_pnl"]) for r in results) == pytest.approx(-3.55)
    row = next(
        r
        for r in stats_book.snapshot()["strategies"]
        if r["strategy_id"] == "trend_continuation"
    )
    assert row["losses"] == 2
    assert row["running_pnl"] == pytest.approx(-3.55)
    # Re-run must not double-count.
    again = reconcile_historical_closes(
        position_ids=[683675942, 683682967],
        deals=deals,
        strategy_bindings={
            683675942: "trend_continuation",
            683682967: "trend_continuation",
        },
        ledger=ledger,
    )
    assert all(r["status"] == "duplicate" for r in again)
    assert row["losses"] == 2


def test_empty_book_without_exit_deal_does_not_invent_pnl(
    ledger, stats_book, attr_store
) -> None:
    pid = 111
    attr_store.bind_fill(
        strategy_id="trend_continuation", engine="soe", ticket=pid, position_id=pid
    )
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(_managed(pid))
    adapter = _Adapter(rows=[], deals=[])  # reliable empty book, no history yet
    sync = force_sync_positions(
        adapter,
        symbol="XAUUSD",
        internal_positions=1,
        position_engine=engine,
        history_deals=[],
    )
    assert sync.reliable is True
    assert pid not in engine._positions  # PME book synced
    assert stats_book.snapshot()["strategies"] == []  # no invented analytics
    assert ledger.pending_ids() == [pid]
