"""Durable shadow book, overlap weak-session BE, AI score wiring helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.institutional_ite_runtime import (
    _pme_ai_scores_from_factors,
    _snapshot_score_factors,
)
from app.domain.institutional_trading.management import shadow_exit_book as book
from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.exit_context import (
    ReversalExitProposal,
)
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import plan_action

OPENED = datetime(2026, 7, 20, 14, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_shadow_book(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    # Reset module memory between tests.
    with book._LOCK:
        book._ENTRIES.clear()
        book._LOADED = False
    yield
    with book._LOCK:
        book._ENTRIES.clear()
        book._LOADED = False


def test_shadow_book_persists_and_marks_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    proposal = ReversalExitProposal(
        structure_broken=True,
        trend_reversed=False,
        reason="test_bos",
        confidence="high",
        against_side="buy",
        is_retracement=False,
        stale_data=False,
    )
    row = book.record_shadow_exit(
        ticket=4242,
        symbol="XAUUSD",
        side="buy",
        proposal=proposal,
        note="unit",
    )
    assert row["ticket"] == 4242
    assert row["outcome"] is None
    path = book._book_path()
    assert path.exists()

    # Simulate restart: clear memory, reload from disk.
    with book._LOCK:
        book._ENTRIES.clear()
        book._LOADED = False
    listed = book.list_shadow_exits(limit=10)
    assert len(listed) == 1
    assert listed[0]["ticket"] == 4242

    n = book.mark_shadow_outcome(ticket=4242, outcome="broker_closed", net_pnl=-1.25)
    assert n == 1
    n2 = book.mark_shadow_outcome(ticket=4242, outcome="broker_closed", net_pnl=-9.0)
    assert n2 == 0  # idempotent
    listed2 = book.list_shadow_exits(limit=10)
    assert listed2[0]["outcome"] == "broker_closed"
    assert listed2[0]["outcome_net_pnl"] == -1.25
    summary = book.shadow_exit_summary()
    assert summary["total"] == 1
    assert summary["with_outcome"] == 1
    assert summary["with_reversal_signal"] == 1


def test_ai_score_helpers_from_factors_and_breakdown():
    snap = SimpleNamespace(
        ai_score=SimpleNamespace(factors={"momentum": 91, "volatility": 40, "bos": 10}),
    )
    factors = _snapshot_score_factors(snap)
    mom, vol = _pme_ai_scores_from_factors(factors)
    assert mom == 91
    assert vol == 40

    snap2 = SimpleNamespace(score_breakdown={"momentum": 12, "volatility": 8})
    mom2, vol2 = _pme_ai_scores_from_factors(_snapshot_score_factors(snap2))
    assert mom2 == 12 and vol2 == 8

    empty_mom, empty_vol = _pme_ai_scores_from_factors({})
    assert empty_mom is None and empty_vol is None


def test_overlap_session_earlier_be_for_scalp():
    cfg = PositionManagementConfig()
    assert "london_ny_overlap" in cfg.weak_management_sessions
    pos = ManagedPosition(
        ticket=7,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal("2295"),
        risk_distance=Decimal("5"),
        opened_at=OPENED,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("2295"),
        current_tp=Decimal("2310"),
        be_moved=False,
        partial_done=False,
        trade_class="SCALP",
        max_favorable_r=Decimal("0.70"),
    )
    # SCALP default be_at=0.80; overlap scales to 0.64 → 0.70R qualifies.
    ctx = PositionManageContext(
        now=OPENED + timedelta(minutes=3),
        current_price=Decimal("2303.5"),
        atr=Decimal("5"),
        mid_price=Decimal("2303.5"),
        spread=Decimal("0.30"),
        market_open=True,
        connection_stable=True,
        position_still_open=True,
        user_id=uuid4(),
        request_id="overlap-be",
        market_session="london_ny_overlap",
        # Leave ai_momentum unset so SCALP profit-extension does not defer BE.
    )
    planned = plan_action(pos, ctx, cfg)
    assert planned.kind == ManageActionKind.BREAK_EVEN
    assert "0.64R" in planned.reason


def test_momentum_fade_fires_when_wired():
    cfg = PositionManagementConfig()
    pos = ManagedPosition(
        ticket=8,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal("2295"),
        risk_distance=Decimal("5"),
        opened_at=OPENED,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("2295"),
        current_tp=Decimal("2310"),
        be_moved=False,
        partial_done=False,
        trade_class="SCALP",
        max_favorable_r=Decimal("0.20"),
    )
    ctx = PositionManageContext(
        now=OPENED + timedelta(minutes=3),
        current_price=Decimal("2301"),
        atr=Decimal("5"),
        mid_price=Decimal("2301"),
        spread=Decimal("0.30"),
        market_open=True,
        connection_stable=True,
        position_still_open=True,
        user_id=uuid4(),
        request_id="fade",
        ai_momentum=25,
    )
    planned = plan_action(pos, ctx, cfg)
    assert planned.kind == ManageActionKind.EMERGENCY_EXIT
    assert "Momentum faded" in planned.reason
