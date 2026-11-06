"""Durable SELL-cascade anchors. No broker orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.close_attribution import (
    BrokerExitEvidence,
    record_broker_confirmed_close,
    reset_close_attribution_ledger_for_tests,
)
from app.domain.institutional_trading.ai_scalping.sell_cascade_anchor_store import (
    PROTECTION_UNAVAILABLE,
    active_anchors,
    evaluate_durable_sell_cascade,
    force_sell_cascade_store_unavailable_for_tests,
    forget_process_cache_for_tests,
    reconcile_anchors,
    record_losing_sell_close,
    recover_sell_cascade_on_startup,
    reset_sell_cascade_store_for_tests,
)
from app.domain.institutional_trading.ai_scalping.sell_cascade_guard import (
    SELL_CASCADE_REJECT,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_WHEN = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_sell_cascade_store_for_tests()
    yield
    reset_sell_cascade_store_for_tests()


def _loss(**overrides: object) -> str:
    payload = {
        "symbol": "XAUUSD",
        "position_id": 8001,
        "entry_price": "4052.50",
        "net_pnl": "-2.68",
        "closed_at": _WHEN,
        "close_outcome": "sl",
        "direction": "SELL",
        "fully_closed": True,
    }
    payload.update(overrides)
    return record_losing_sell_close(**payload)  # type: ignore[arg-type]


def test_losing_sell_creates_durable_anchor() -> None:
    assert _loss() == "created"
    rows, trusted = active_anchors("XAUUSD")
    assert trusted is True
    assert len(rows) == 1
    assert rows[0].position_id == 8001
    assert rows[0].entry_price == Decimal("4052.50")
    assert rows[0].net_pnl == Decimal("-2.68")
    assert rows[0].close_outcome == "sl"
    assert rows[0].status == "active"


def test_winning_sell_does_not_create_anchor() -> None:
    assert _loss(net_pnl="1.25", close_outcome="tp", position_id=8002) == "ignored_win"
    rows, _trusted = active_anchors("XAUUSD")
    assert rows == []


def test_partial_close_does_not_create_final_loss_anchor() -> None:
    assert _loss(fully_closed=False, position_id=8003) == "ignored_partial"
    rows, _trusted = active_anchors("XAUUSD")
    assert rows == []


def test_duplicate_close_is_idempotent() -> None:
    assert _loss() == "created"
    assert _loss() == "duplicate"
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1


def test_anchor_survives_worker_restart_and_blocks_before_new_sell() -> None:
    assert _loss() == "created"
    forget_process_cache_for_tests()
    summary = recover_sell_cascade_on_startup(adapter=None)
    assert summary["trusted"] is True
    assert summary["restored"] == 1
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4055"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == SELL_CASCADE_REJECT


def test_sell_reentry_at_or_above_failed_entry_is_blocked() -> None:
    assert _loss(entry_price="4050") == "created"
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4050"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == SELL_CASCADE_REJECT
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4060"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == SELL_CASCADE_REJECT


def test_price_reclaim_below_failed_entry_releases_anchor() -> None:
    assert _loss(position_id=8100, entry_price="4060") == "created"
    assert _loss(position_id=8101, entry_price="4050") == "created"
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4055"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == SELL_CASCADE_REJECT
    left, _trusted = active_anchors("XAUUSD")
    assert [row.position_id for row in left] == [8101]
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4049.9"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "reclaimed_failed_sell_entry"
    assert active_anchors("XAUUSD")[0] == []


def test_bearish_reversal_releases_the_symbol_anchor() -> None:
    assert _loss() == "created"
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4060"),
        reversal_confirmed=True,
    )
    assert blocked is False
    assert why == "bearish_reversal_confirmed"
    assert active_anchors("XAUUSD")[0] == []


def test_buy_entries_are_not_blocked_by_sell_anchors() -> None:
    assert _loss() == "created"
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4060"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "not_sell"
    rows, _trusted = active_anchors("XAUUSD")
    assert len(rows) == 1


def test_persistence_outage_blocks_sell_fail_closed() -> None:
    assert _loss() == "created"
    force_sell_cascade_store_unavailable_for_tests(True)
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4000"),
        reversal_confirmed=True,
    )
    assert blocked is True
    assert why == PROTECTION_UNAVAILABLE
    buy_blocked, buy_why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4000"),
        reversal_confirmed=False,
    )
    assert buy_blocked is False
    assert buy_why == "not_sell"


def test_missing_broker_history_fails_closed_for_new_sell() -> None:
    """Live adapter with unreadable history must not allow unprotected SELL."""

    class _Adapter:
        def list_positions(self) -> list[object]:
            return []

        def account_snapshot(self) -> object:
            return type("Snap", (), {"login": 12479147})()

        def history_deals(self, *_a: object, **_k: object) -> list[object]:
            raise RuntimeError("history unavailable")

    assert _loss() == "created"
    summary = recover_sell_cascade_on_startup(adapter=_Adapter())
    assert summary["trusted"] is False
    assert summary["history_ok"] is False
    blocked, why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=Decimal("4000"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == PROTECTION_UNAVAILABLE
    buy_blocked, buy_why = evaluate_durable_sell_cascade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=Decimal("4000"),
        reversal_confirmed=False,
    )
    assert buy_blocked is False
    assert buy_why == "not_sell"


def test_broker_reconciliation_releases_stale_open_and_winning_rows() -> None:
    assert _loss(position_id=8200, entry_price="4050") == "created"
    assert _loss(position_id=8201, entry_price="4060") == "created"
    assert _loss(position_id=8202, entry_price="4070") == "created"
    stats = reconcile_anchors(
        symbol="XAUUSD",
        open_position_ids={8200},
        broker_nets={8201: Decimal("0.80"), 8202: Decimal("-1.10")},
    )
    assert stats["still_open"] == 1
    assert stats["broker_win"] == 1
    assert stats["kept"] == 1
    rows, _trusted = active_anchors("XAUUSD")
    assert [row.position_id for row in rows] == [8202]


def test_account_mismatch_releases_foreign_anchor() -> None:
    assert (
        record_losing_sell_close(
            symbol="XAUUSD",
            position_id=8300,
            entry_price="4050",
            net_pnl="-2",
            closed_at=_WHEN,
            direction="SELL",
            fully_closed=True,
            broker_login=12260878,
        )
        == "created"
    )
    stats = reconcile_anchors(
        symbol="XAUUSD",
        open_position_ids=set(),
        broker_nets=None,
        broker_login=12479147,
    )
    assert stats["not_on_account"] == 1
    assert active_anchors("XAUUSD")[0] == []


def test_broker_confirmed_close_arms_sell_anchor_from_evidence(
    tmp_path: Path,
) -> None:
    ledger = reset_close_attribution_ledger_for_tests(tmp_path / "ledger.json")
    evidence = BrokerExitEvidence(
        position_id=8400,
        symbol="XAUUSD",
        exit_deal_id=99001,
        entry_deal_id=99000,
        exit_price=4058.20,
        entry_price=4055.10,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=-3.10,
        commission=0.0,
        swap=0.0,
        net_pnl=-3.10,
        close_reason="[sl 4058.20]",
        side="sell",
        hold_seconds=90.0,
    )
    record_broker_confirmed_close(
        evidence=evidence, strategy_id="ite_scalping", ledger=ledger
    )
    rows, trusted = active_anchors("XAUUSD")
    assert trusted is True
    assert len(rows) == 1
    assert rows[0].position_id == 8400
    assert rows[0].entry_price == Decimal("4055.10")


def test_buy_loss_evidence_does_not_create_sell_anchor(tmp_path: Path) -> None:
    ledger = reset_close_attribution_ledger_for_tests(tmp_path / "ledger2.json")
    evidence = BrokerExitEvidence(
        position_id=8401,
        symbol="XAUUSD",
        exit_deal_id=99002,
        entry_deal_id=99003,
        exit_price=4050.00,
        entry_price=4055.10,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=-5.10,
        commission=0.0,
        swap=0.0,
        net_pnl=-5.10,
        close_reason="[sl 4050.00]",
        side="buy",
        hold_seconds=60.0,
    )
    record_broker_confirmed_close(
        evidence=evidence, strategy_id="ite_scalping", ledger=ledger
    )
    rows, _trusted = active_anchors("XAUUSD")
    assert rows == []
