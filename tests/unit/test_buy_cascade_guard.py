"""BUY cascade guard — unresolved decline vs confirmed reversal."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.buy_cascade_guard import (
    BUY_CASCADE_REJECT,
    bullish_reversal_since,
    buy_cascade_blocked,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    SymbolStateBook,
)
from app.domain.institutional_trading.decision_models import TradeDirection


@pytest.mark.unit
def test_lower_buy_after_loss_is_blocked() -> None:
    blocked, why = buy_cascade_blocked(
        direction="BUY",
        entry_price=Decimal("4100"),
        anchor=Decimal("4110"),
        reversal_confirmed=False,
    )
    assert blocked is True
    assert why == BUY_CASCADE_REJECT


@pytest.mark.unit
def test_reclaim_above_failed_entry_is_allowed() -> None:
    blocked, why = buy_cascade_blocked(
        direction="BUY",
        entry_price=Decimal("4112"),
        anchor=Decimal("4110"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "reclaimed_failed_buy_entry"


@pytest.mark.unit
def test_bullish_reversal_allows_buy_below_anchor() -> None:
    blocked, why = buy_cascade_blocked(
        direction="BUY",
        entry_price=Decimal("4090"),
        anchor=Decimal("4110"),
        reversal_confirmed=True,
    )
    assert blocked is False
    assert why == "bullish_reversal_confirmed"


@pytest.mark.unit
def test_sell_is_never_cascade_blocked() -> None:
    blocked, why = buy_cascade_blocked(
        direction="SELL",
        entry_price=Decimal("4000"),
        anchor=Decimal("4110"),
        reversal_confirmed=False,
    )
    assert blocked is False
    assert why == "not_buy"


@pytest.mark.unit
def test_missing_anchor_fail_open() -> None:
    blocked, _why = buy_cascade_blocked(
        direction="BUY",
        entry_price=Decimal("4000"),
        anchor=None,
        reversal_confirmed=False,
    )
    assert blocked is False


@pytest.mark.unit
def test_symbol_book_sets_and_clears_anchor() -> None:
    book = SymbolStateBook()
    book.note_closed(
        "XAUUSD",
        pnl=-2.5,
        direction="BUY",
        entry_price="4114.9",
        closed_at=datetime(2026, 11, 5, 19, 20, tzinfo=UTC),
    )
    state = book.get("XAUUSD")
    assert state.cascade_anchor == Decimal("4114.9")
    book.note_closed("XAUUSD", pnl=1.2, direction="BUY", entry_price="4120")
    assert book.get("XAUUSD").cascade_anchor is None


@pytest.mark.unit
def test_sell_close_does_not_clear_buy_anchor() -> None:
    book = SymbolStateBook()
    book.note_closed("XAUUSD", pnl=-1.0, direction="BUY", entry_price="4100")
    book.note_closed("XAUUSD", pnl=0.4, direction="SELL", entry_price="4090")
    assert book.get("XAUUSD").cascade_anchor == Decimal("4100")


@pytest.mark.unit
def test_bullish_choch_after_close_is_reversal() -> None:
    since = datetime(2026, 11, 5, 19, 0, tzinfo=UTC)
    event = SimpleNamespace(
        kind="CHOCH",
        previous_trend=TradeDirection.SELL,
        broken_at=datetime(2026, 11, 5, 19, 30, tzinfo=UTC),
    )
    older = SimpleNamespace(
        kind="CHOCH",
        previous_trend=TradeDirection.SELL,
        broken_at=datetime(2026, 11, 5, 18, 0, tzinfo=UTC),
    )
    struct = SimpleNamespace(
        changes_of_character=(older, event),
        breaks_of_structure=(),
    )
    snapshot = SimpleNamespace(structure_by_tf={"M5": struct})
    assert bullish_reversal_since(snapshot, since) is True
    assert (
        bullish_reversal_since(snapshot, datetime(2026, 11, 5, 20, 0, tzinfo=UTC))
        is False
    )
    assert bullish_reversal_since(snapshot, None) is False
