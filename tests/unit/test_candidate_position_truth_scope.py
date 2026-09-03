"""Regression: candidate-scoped position truth vs gold-forced overwrite."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.mt5_position_truth import (
    PositionTruthSync,
    apply_mt5_position_truth,
    candidate_position_truth_symbol,
    force_sync_positions,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _qf(
    *,
    symbol: str,
    ticket: int,
    side: str = "BUY",
    open_price: str = "2650.0",
    volume: str = "0.01",
    magic: int = QUANTFORG_MAGIC,
) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
        symbol=symbol,
        side=side,
        open_price=open_price,
        volume=volume,
        remaining_volume=volume,
        magic=magic,
        profit="1",
        comment="ite:v1",
    )


class _Adapter:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def list_positions(self) -> list:
        return list(self._rows)


def _account(*, open_n: int = 0, dirs=(), entries=()) -> AccountRiskState:
    return AccountRiskState(
        equity=Decimal("10000"),
        open_positions=open_n,
        already_in_trade=open_n > 0,
        account_open_positions=open_n,
        open_directions=tuple(dirs),
        open_entries=tuple(entries),
    )


def _addon_incomplete(account: AccountRiskState) -> bool:
    """Mirror institutional_decision_pipeline incomplete-add-on gate."""
    return bool(
        account.open_positions > 0
        and not account.open_directions
        and not account.open_entries
    )


def test_candidate_symbol_gold_canonicalizes_to_broker_form() -> None:
    assert candidate_position_truth_symbol("XAUUSD") == "XAUUSD_i"
    assert candidate_position_truth_symbol("XAUUSD_i") == "XAUUSD_i"


def test_candidate_symbol_non_gold_not_coerced_to_gold() -> None:
    for sym in ("EURCHF", "NZDCHF", "BTCUSD", "NDXUSD", "LTCUSD", "EURJPY"):
        out = candidate_position_truth_symbol(sym)
        assert out == sym
        assert not out.upper().startswith("XAU")


def test_gold_open_eurchf_candidate_no_incomplete_addon() -> None:
    """CASE A — production defect: Gold QF open must not poison EURCHF."""
    rows = [_qf(symbol="XAUUSD_i", ticket=579658107, open_price="2650")]
    sync = force_sync_positions(
        _Adapter(rows),
        symbol=candidate_position_truth_symbol("EURCHF"),
        internal_positions=0,
    )
    assert sync.symbol == "EURCHF"
    assert sync.mt5_positions == 1
    assert sync.quantforg_positions == 0
    account = apply_mt5_position_truth(
        _account(open_n=0, dirs=(), entries=()),
        sync,
    )
    assert account.account_open_positions == 1
    assert account.open_positions == 0
    assert account.open_directions == ()
    assert account.open_entries == ()
    assert _addon_incomplete(account) is False


def test_gold_open_nzdchf_candidate_no_incomplete_addon() -> None:
    rows = [_qf(symbol="XAUUSD_i", ticket=1)]
    sync = force_sync_positions(
        _Adapter(rows),
        symbol=candidate_position_truth_symbol("NZDCHF"),
        internal_positions=0,
    )
    account = apply_mt5_position_truth(_account(), sync)
    assert account.open_positions == 0
    assert account.account_open_positions == 1
    assert _addon_incomplete(account) is False


@pytest.mark.parametrize("cand", ["BTCUSD", "NDXUSD", "LTCUSD"])
def test_gold_open_priority_candidates_independent(cand: str) -> None:
    rows = [_qf(symbol="XAUUSD_i", ticket=42)]
    sync = force_sync_positions(
        _Adapter(rows),
        symbol=candidate_position_truth_symbol(cand),
        internal_positions=0,
    )
    account = apply_mt5_position_truth(_account(), sync)
    assert sync.quantforg_positions == 0
    assert account.open_positions == 0
    assert account.account_open_positions == 1
    assert _addon_incomplete(account) is False


def test_same_symbol_incomplete_book_still_fail_closed() -> None:
    """CASE D — EURCHF QF open but unparseable sides/entries → fail closed."""
    bad = SimpleNamespace(
        ticket=9,
        symbol="EURCHF",
        side="",
        open_price="0",
        volume="0.01",
        magic=QUANTFORG_MAGIC,
        comment="ite:v1",
    )
    sync = force_sync_positions(
        _Adapter([bad]),
        symbol="EURCHF",
        internal_positions=0,
    )
    assert sync.quantforg_positions == 1
    account = apply_mt5_position_truth(_account(), sync)
    assert account.open_positions == 1
    assert account.open_directions == ()
    assert account.open_entries == ()
    assert _addon_incomplete(account) is True


def test_same_symbol_complete_book_preserves_addon_facts() -> None:
    rows = [
        _qf(
            symbol="EURCHF",
            ticket=11,
            side="SELL",
            open_price="0.9390",
        )
    ]
    sync = force_sync_positions(_Adapter(rows), symbol="EURCHF")
    account = apply_mt5_position_truth(_account(), sync)
    assert account.open_positions == 1
    assert account.open_directions == ("SELL",)
    assert account.open_entries == (Decimal("0.9390"),)
    assert _addon_incomplete(account) is False


def test_apply_truth_cannot_keep_stale_dirs_when_qf_zero() -> None:
    """Gold sync must not leave prior dirs with qf overwritten — use candidate sync."""
    gold_rows = [_qf(symbol="XAUUSD_i", ticket=1, side="BUY", open_price="2650")]
    # Wrong historical call shape: gold sync after candidate had empty book.
    sync_gold = force_sync_positions(_Adapter(gold_rows), symbol="XAUUSD_i")
    poisoned = apply_mt5_position_truth(
        _account(open_n=0, dirs=(), entries=()),
        sync_gold,
    )
    # Gold sync correctly reports gold QF=1 with book facts (not incomplete).
    assert poisoned.open_positions == 1
    assert poisoned.open_directions == ("BUY",)
    assert _addon_incomplete(poisoned) is False

    # Candidate EURCHF sync after gold open → flat, clears any stale state.
    sync_fx = force_sync_positions(
        _Adapter(gold_rows),
        symbol=candidate_position_truth_symbol("EURCHF"),
    )
    fixed = apply_mt5_position_truth(
        _account(
            open_n=1,
            dirs=("BUY",),
            entries=(Decimal("2650"),),
        ),
        sync_fx,
    )
    assert fixed.open_positions == 0
    assert fixed.open_directions == ()
    assert fixed.open_entries == ()
    assert fixed.account_open_positions == 1
    assert _addon_incomplete(fixed) is False


def test_apply_truth_refreshes_book_from_sync_rows() -> None:
    sync = PositionTruthSync(
        mt5_positions=2,
        internal_positions=0,
        repaired=False,
        symbol="BTCUSD",
        tickets=(1, 2),
        quantforg_positions=1,
        quantforg_tickets=(2,),
        rows=(
            _qf(symbol="XAUUSD_i", ticket=1),
            _qf(symbol="BTCUSD", ticket=2, side="BUY", open_price="70000"),
        ),
    )
    account = apply_mt5_position_truth(_account(open_n=9, dirs=(), entries=()), sync)
    assert account.open_positions == 1
    assert account.account_open_positions == 2
    assert account.open_directions == ("BUY",)
    assert account.open_entries == (Decimal("70000"),)
    assert _addon_incomplete(account) is False
