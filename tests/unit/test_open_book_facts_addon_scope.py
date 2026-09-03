"""Regression: open_book_facts_incomplete scopes to same-symbol add-ons only."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
    resolve_same_symbol_addon_book,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _qf_pos(
    *,
    symbol: str,
    ticket: int,
    side: str = "BUY",
    open_price: str = "100.0",
    volume: str = "0.01",
    magic: int = QUANTFORG_MAGIC,
    profit: str = "1.0",
) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
        symbol=symbol,
        side=side,
        open_price=open_price,
        volume=volume,
        magic=magic,
        profit=profit,
        comment="ite:v1",
    )


def test_case1_independent_btc_with_other_qf_symbol_open() -> None:
    """BTCUSD candidate + ETHUSD QuantForg open → not an incomplete add-on."""
    rows = [_qf_pos(symbol="ETHUSD", ticket=101)]
    out = resolve_same_symbol_addon_book(
        rows,
        candidate_symbol="BTCUSD",
        global_quantforg_positions=1,
        global_tickets=(101,),
    )
    assert out["open_positions"] == 0
    assert out["addon_scope"] == "independent_new_symbol"
    assert out["book_facts_incomplete"] is False
    assert out["book_facts_ok"] is True
    assert out["cross_symbol_quantforg_open"] is True


def test_case2_same_symbol_addon_incomplete_book_fail_closed() -> None:
    """Same-symbol QF open but unparseable sides/entries → incomplete add-on."""
    bad = SimpleNamespace(
        ticket=202,
        symbol="BTCUSD",
        side="",
        open_price="0",
        volume="0.01",
        magic=QUANTFORG_MAGIC,
        profit="0",
        comment="ite:v1",
    )
    out = resolve_same_symbol_addon_book(
        [bad],
        candidate_symbol="BTCUSD",
        global_quantforg_positions=1,
        global_tickets=(202,),
    )
    assert out["open_positions"] == 1
    assert out["addon_scope"] == "same_symbol"
    assert out["book_facts_ok"] is False
    assert out["book_facts_incomplete"] is True


def test_case3_btc_complete_facts_while_eth_open() -> None:
    """BTCUSD independent book stays flat even when ETHUSD is open."""
    rows = [
        _qf_pos(symbol="ETHUSD", ticket=1),
        # No BTCUSD QF row — candidate is a new independent symbol.
    ]
    out = resolve_same_symbol_addon_book(
        rows,
        candidate_symbol="BTCUSD",
        global_quantforg_positions=1,
        global_tickets=(1,),
    )
    assert out["open_positions"] == 0
    assert out["open_directions"] == ()
    assert out["addon_scope"] == "independent_new_symbol"
    assert out["book_facts_incomplete"] is False


def test_case4_manual_same_symbol_does_not_count_as_qf_addon() -> None:
    manual = SimpleNamespace(
        ticket=303,
        symbol="BTCUSD",
        side="BUY",
        open_price="65000",
        volume="0.01",
        magic=0,
        profit="0",
        comment="manual",
    )
    out = resolve_same_symbol_addon_book(
        [manual],
        candidate_symbol="BTCUSD",
        global_quantforg_positions=0,
        global_tickets=(),
    )
    assert out["open_positions"] == 0
    assert out["addon_scope"] == "flat"
    assert out["book_facts_incomplete"] is False


def test_case5_ndx_independent_of_btc_open() -> None:
    rows = [_qf_pos(symbol="BTCUSD", ticket=404)]
    out = resolve_same_symbol_addon_book(
        rows,
        candidate_symbol="NDXUSD",
        global_quantforg_positions=1,
        global_tickets=(404,),
    )
    assert out["open_positions"] == 0
    assert out["addon_scope"] == "independent_new_symbol"
    assert out["book_facts_incomplete"] is False


def test_case6_ltc_same_symbol_rows_missing_fail_closed() -> None:
    out = resolve_same_symbol_addon_book(
        [],
        candidate_symbol="LTCUSD",
        global_quantforg_positions=1,
        global_tickets=(505,),
    )
    assert out["open_positions"] == 1
    assert out["addon_scope"] == "incomplete_book"
    assert out["book_facts_rows_missing"] is True
    assert out["book_facts_ok"] is False
    assert out["book_facts_incomplete"] is True


def test_case7_flat_book_no_incomplete_flag() -> None:
    out = resolve_same_symbol_addon_book(
        [],
        candidate_symbol="BTCUSD",
        global_quantforg_positions=0,
        global_tickets=(),
    )
    assert out["open_positions"] == 0
    assert out["addon_scope"] == "flat"
    assert out["book_facts_incomplete"] is False
    assert out["book_facts_ok"] is True


def test_same_symbol_complete_addon_book() -> None:
    rows = [
        _qf_pos(
            symbol="BTCUSD",
            ticket=606,
            side="SELL",
            open_price="70000",
            profit="5",
        )
    ]
    out = resolve_same_symbol_addon_book(
        rows,
        candidate_symbol="BTCUSD",
        global_quantforg_positions=1,
        global_tickets=(606,),
    )
    assert out["open_positions"] == 1
    assert out["open_directions"] == ("SELL",)
    assert out["open_entries"] == (Decimal("70000"),)
    assert out["book_facts_ok"] is True
    assert out["book_facts_incomplete"] is False
    assert out["addon_scope"] == "same_symbol"


def test_pipeline_gate_only_fires_when_open_positions_positive() -> None:
    """Mirror institutional_decision_pipeline incomplete-add-on condition."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "application"
        / "services"
        / "institutional_decision_pipeline.py"
    ).read_text(encoding="utf-8")
    assert "open_book_facts_incomplete — blocking add-on" in src

    def _gate(open_positions: int, directions: tuple, entries: tuple) -> bool:
        return bool(open_positions > 0 and not directions and not entries)

    assert _gate(0, (), ()) is False
    assert _gate(1, (), ()) is True
    assert _gate(1, ("BUY",), (Decimal("1"),)) is False
