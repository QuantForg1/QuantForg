"""Durable BUY-cascade anchors. No broker orders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.close_attribution import (
    BrokerExitEvidence,
    record_broker_confirmed_close,
    reset_close_attribution_ledger_for_tests,
)
from app.domain.institutional_trading.ai_scalping.buy_cascade_anchor_store import (
    PROTECTION_UNAVAILABLE,
    active_anchors,
    evaluate_durable_buy_cascade,
    force_buy_cascade_store_unavailable_for_tests,
    forget_process_cache_for_tests,
    reconcile_anchors,
    record_losing_buy_close,
    recover_buy_cascade_on_startup,
    reset_buy_cascade_store_for_tests,
)
from app.domain.institutional_trading.ai_scalping.buy_cascade_guard import (
    BUY_CASCADE_REJECT,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_WHEN = datetime(2026, 11, 5, 18, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_buy_cascade_store_for_tests()
    yield
    reset_buy_cascade_store_for_tests()


def _loss(**overrides: object) -> str:
    payload = {
        "symbol": "XAUUSD",
        "position_id": 9001,
        "entry_price": "4114.90",
        "net_pnl": "-2.40",
        "closed_at": _WHEN,
        "close_outcome": "sl",
        "direction": "BUY",
        "fully_closed": True,
    }
    payload.update(overrides)
    return record_losing_buy_close(**payload)  # type: ignore[arg-type]


def test_losing_buy_creates_durable_anchor() -> None:
    assert _loss() == "created"
    rows, trusted = active_anchors("XAUUSD")
    assert trusted is True
    assert len(rows) == 1
    assert rows[0].position_id == 9001
    assert rows[0].entry_price == Decimal("4114.90")
    assert rows[0].net_pnl == Decimal("-2.40")
    assert rows[0].close_outcome == "sl"
    assert rows[0].status == "active"
    assert rows[0].closed_at == _WHEN


def test_winning_buy_does_not_create_anchor() -> None:
    assert _loss(net_pnl="1.25", close_outcome="tp", position_id=9002) == "ignored_win"
    rows, _trusted = active_anchors("XAUUSD")
    assert rows == []


def test_partial_close_does_not_create_final_loss_anchor() -> None:
    assert _loss(fully_closed=False, position_id=9003) == "ignored_partial"
    rows, _trusted = active_anchors("XAUUSD")
    assert rows == []


def test_duplicate_close_is_idempotent() -> None:
    assert _loss() == "created"
    assert _loss() == "duplicate"
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1


def test_anchor_survives_worker_restart_and_blocks_before_new_buy() -> None:
    assert _loss() == "created"
    forget_process_cache_for_tests()
    summary = recover_buy_cascade_on_startup(adapter=None)
    assert summary["trusted"] is True
    assert summary["restored"] == 1
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4110"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == BUY_CASCADE_REJECT


def test_broker_reconciliation_releases_stale_open_and_winning_rows() -> None:
    assert _loss(position_id=9100, entry_price="4100") == "created"
    assert _loss(position_id=9101, entry_price="4120") == "created"
    assert _loss(position_id=9102, entry_price="4130") == "created"
    stats = reconcile_anchors(
        symbol="XAUUSD",
        open_position_ids={9100},
        broker_nets={9101: Decimal("0.80"), 9102: Decimal("-1.10")},
    )
    assert stats["still_open"] == 1
    assert stats["broker_win"] == 1
    assert stats["kept"] == 1
    rows, _trusted = active_anchors("XAUUSD")
    assert [row.position_id for row in rows] == [9102]


def test_missing_broker_history_does_not_drop_anchor() -> None:
    assert _loss(position_id=9200) == "created"
    stats = reconcile_anchors(
        symbol="XAUUSD",
        open_position_ids=set(),
        broker_nets={},
    )
    assert stats["kept"] == 1
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1


def test_price_reclaim_releases_only_anchors_below_the_new_entry() -> None:
    assert _loss(position_id=9300, entry_price="4100") == "created"
    assert _loss(position_id=9301, entry_price="4120") == "created"
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4110"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == BUY_CASCADE_REJECT
    left, _trusted = active_anchors("XAUUSD")
    assert [row.position_id for row in left] == [9301]
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4120.1"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "reclaimed_failed_buy_entry"
    assert active_anchors("XAUUSD")[0] == []


def test_bullish_reversal_releases_the_symbol_anchor() -> None:
    assert _loss() == "created"
    assert _loss(symbol="EURUSD", position_id=9400, entry_price="1.08") == "created"
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4100"),
        reversal_confirmed=True,
    )
    assert blocked is False
    assert why == "bullish_reversal_confirmed"
    assert active_anchors("XAUUSD")[0] == []
    other, _trusted = active_anchors("EURUSD")
    assert [row.position_id for row in other] == [9400]


def test_sell_entries_do_not_block_or_clear_the_anchor() -> None:
    assert _loss() == "created"
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4100"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "not_buy"
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1


def test_persistence_outage_blocks_buy_and_preserves_anchor() -> None:
    assert _loss() == "created"
    force_buy_cascade_store_unavailable_for_tests(True)
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4200"),
        reversal_confirmed=True,
    )
    assert blocked is True
    assert why == PROTECTION_UNAVAILABLE
    sell_blocked, sell_why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4100"),
        reversal_confirmed=False,
    )
    assert sell_blocked is False
    assert sell_why == "not_buy"
    assert (
        record_losing_buy_close(
            symbol="XAUUSD",
            position_id=9500,
            entry_price="4000",
            net_pnl="-1",
            direction="BUY",
            fully_closed=True,
        )
        == "untrusted"
    )
    force_buy_cascade_store_unavailable_for_tests(False)
    rows, trusted = active_anchors("XAUUSD")
    assert trusted is True
    assert [row.position_id for row in rows] == [9001]


def test_repeated_recovery_does_not_duplicate_or_stick_a_stale_open_ticket() -> None:
    assert _loss(position_id=9600) == "created"
    assert _loss(position_id=9601, entry_price="4200") == "created"

    class _Adapter:
        def list_positions(self) -> list[object]:
            return [type("P", (), {"ticket": 9600})()]

        def history_deals(self) -> list[object]:
            raise RuntimeError("history down")

    first = recover_buy_cascade_on_startup(_Adapter())
    second = recover_buy_cascade_on_startup(_Adapter())
    assert first["restored"] == 2
    assert second["restored"] == 1
    assert first["reconciled"]["XAUUSD"]["still_open"] == 1
    assert second["reconciled"]["XAUUSD"]["kept"] == 1
    rows, _trusted = active_anchors("XAUUSD")
    assert [row.position_id for row in rows] == [9601]


def test_broker_confirmed_losing_buy_arms_anchor_and_winner_does_not(
    tmp_path: Path,
) -> None:
    ledger = reset_close_attribution_ledger_for_tests(tmp_path / "ledger.json")
    loss = BrokerExitEvidence(
        position_id=9701,
        symbol="XAUUSD",
        exit_deal_id=501,
        entry_deal_id=500,
        exit_price=4110.0,
        entry_price=4114.9,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=-2.4,
        commission=0.0,
        swap=0.0,
        net_pnl=-2.4,
        close_reason="sl",
        side="buy",
        hold_seconds=60.0,
    )
    record_broker_confirmed_close(evidence=loss, source="test", ledger=ledger)
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1
    assert rows[0].entry_price == Decimal("4114.9")
    assert rows[0].position_id == 9701
    record_broker_confirmed_close(evidence=loss, source="test", ledger=ledger)
    assert len(active_anchors("XAUUSD")[0]) == 1
    win = BrokerExitEvidence(
        position_id=9702,
        symbol="XAUUSD",
        exit_deal_id=503,
        entry_deal_id=502,
        exit_price=4120.0,
        entry_price=4114.9,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=1.5,
        commission=0.0,
        swap=0.0,
        net_pnl=1.5,
        close_reason="tp",
        side="buy",
        hold_seconds=30.0,
    )
    record_broker_confirmed_close(evidence=win, source="test", ledger=ledger)
    assert active_anchors("XAUUSD")[0] == []


def _deal(
    *,
    ticket: int,
    position_id: int,
    deal_type: str,
    price: float,
    profit: float,
    minutes: int,
    side: str = "buy",
) -> dict[str, object]:
    moment = _WHEN + timedelta(minutes=minutes)
    return {
        "ticket": ticket,
        "position_id": position_id,
        "symbol": "XAUUSD",
        "side": side,
        "volume": 0.01,
        "price": price,
        "profit": profit,
        "commission": 0.0,
        "swap": 0.0,
        "deal_type": deal_type,
        "time": moment.isoformat(),
        "comment": "",
        "magic": 260720,
    }


class _HistoryAdapter:
    def __init__(self, deals: list[dict[str, object]]) -> None:
        self._deals = deals

    def list_positions(self) -> list[object]:
        return []

    def history_deals(self) -> list[dict[str, object]]:
        return self._deals


def test_restart_backfill_arms_only_losses_after_the_last_winning_buy() -> None:
    deals = [
        _deal(
            ticket=1,
            position_id=9801,
            deal_type="entry_in",
            price=4100,
            profit=0,
            minutes=0,
        ),
        _deal(
            ticket=2,
            position_id=9801,
            deal_type="entry_out",
            price=4098,
            profit=-1.5,
            minutes=1,
        ),
        _deal(
            ticket=3,
            position_id=9802,
            deal_type="entry_in",
            price=4105,
            profit=0,
            minutes=2,
        ),
        _deal(
            ticket=4,
            position_id=9802,
            deal_type="entry_out",
            price=4108,
            profit=1.2,
            minutes=3,
        ),
        _deal(
            ticket=5,
            position_id=9803,
            deal_type="entry_in",
            price=4114.9,
            profit=0,
            minutes=4,
        ),
        _deal(
            ticket=6,
            position_id=9803,
            deal_type="entry_out",
            price=4112,
            profit=-2.2,
            minutes=5,
        ),
    ]
    summary = recover_buy_cascade_on_startup(_HistoryAdapter(deals))
    assert summary["backfilled"] == 1
    rows, trusted = active_anchors("XAUUSD")
    assert trusted is True
    assert [row.position_id for row in rows] == [9803]
    assert rows[0].entry_price == Decimal("4114.9")
    forget_process_cache_for_tests()
    again = recover_buy_cascade_on_startup(_HistoryAdapter(deals))
    assert again["backfilled"] == 0
    assert [row.position_id for row in active_anchors("XAUUSD")[0]] == [9803]


def test_released_anchor_is_not_recreated_from_broker_history() -> None:
    assert _loss(position_id=9901, entry_price="4114.9") == "created"
    blocked, why = evaluate_durable_buy_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4120"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "reclaimed_failed_buy_entry"
    deals = [
        _deal(
            ticket=11,
            position_id=9901,
            deal_type="entry_in",
            price=4114.9,
            profit=0,
            minutes=0,
        ),
        _deal(
            ticket=12,
            position_id=9901,
            deal_type="entry_out",
            price=4112,
            profit=-2.2,
            minutes=1,
        ),
    ]
    forget_process_cache_for_tests()
    summary = recover_buy_cascade_on_startup(_HistoryAdapter(deals))
    assert summary["backfilled"] == 0
    assert active_anchors("XAUUSD")[0] == []
