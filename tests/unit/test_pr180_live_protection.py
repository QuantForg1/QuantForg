"""PR #180 — LIVE close-on-confirmed-reversal, M1 flags, SELL cascade."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.sell_cascade_anchor_store import (
    evaluate_durable_sell_cascade,
    record_losing_sell_close,
    reset_sell_cascade_store_for_tests,
)
from app.domain.institutional_trading.ai_scalping.sell_cascade_guard import (
    sell_cascade_blocked,
)
from app.domain.institutional_trading.m1_micro.config import (
    m1_live_submit_enabled,
    m1_micro_enabled,
)
from app.domain.institutional_trading.management.close_then_reverse import (
    evaluate_close_then_reverse,
)
from app.domain.institutional_trading.management.config import (
    DEFAULT_PME_CONFIG,
    live_reversal_exits_resolved,
)
from app.domain.institutional_trading.management.exit_context import (
    propose_reversal_exit,
)
from app.domain.institutional_trading.management.reversal_close_dedup import (
    clear_reversal_close,
    mark_reversal_close_requested,
    reset_reversal_close_dedup_for_tests,
    should_allow_reversal_close,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture(autouse=True)
def _clean_stores() -> None:
    reset_sell_cascade_store_for_tests()
    reset_reversal_close_dedup_for_tests()
    yield
    reset_sell_cascade_store_for_tests()
    reset_reversal_close_dedup_for_tests()


class TestLiveReversalFlags:
    def test_default_live_reversal_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QUANTFORG_LIVE_REVERSAL_EXITS", raising=False)
        assert DEFAULT_PME_CONFIG.live_reversal_exits_enabled is True
        assert live_reversal_exits_resolved(default=True) is True

    def test_env_can_disable_live_reversal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("QUANTFORG_LIVE_REVERSAL_EXITS", "false")
        assert live_reversal_exits_resolved(default=True) is False

    def test_pullback_never_confirms_live_structure(self) -> None:
        p = propose_reversal_exit(position_side="buy", ltf_only_noise=True)
        assert p.structure_broken is False
        assert p.classification == "temporary_m1_pullback"

    def test_confirmed_reversal_feeds_close_not_reverse(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            choch_against=True,
            htf_agrees_against=True,
        )
        plan = evaluate_close_then_reverse(
            proposal=p,
            position_open_broker=True,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=False,
        )
        assert plan.submit_close is True
        assert plan.submit_opposite is False


class TestReversalCloseDedup:
    def test_duplicate_close_blocked(self) -> None:
        assert should_allow_reversal_close(42) is True
        mark_reversal_close_requested(42)
        assert should_allow_reversal_close(42) is False
        clear_reversal_close(42)
        assert should_allow_reversal_close(42) is True


class TestM1Flags:
    def test_evaluation_on_submit_off_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
        monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
        assert m1_micro_enabled() is True
        assert m1_live_submit_enabled() is False

    def test_submit_requires_explicit_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
        monkeypatch.setenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", "true")
        assert m1_live_submit_enabled() is True


class TestSellCascade:
    def test_blocks_higher_sell_after_loss(self) -> None:
        blocked, reason = sell_cascade_blocked(
            direction="SELL",
            entry_price=Decimal("2400"),
            anchor=Decimal("2390"),
            reversal_confirmed=False,
        )
        assert blocked is True
        assert reason == "SELL_CASCADE_UNRESOLVED_RALLY"

    def test_allows_reclaim_below_failed_entry(self) -> None:
        blocked, reason = sell_cascade_blocked(
            direction="SELL",
            entry_price=Decimal("2380"),
            anchor=Decimal("2390"),
            reversal_confirmed=False,
        )
        assert blocked is False
        assert reason == "reclaimed_failed_sell_entry"

    def test_does_not_block_buy(self) -> None:
        blocked, reason = sell_cascade_blocked(
            direction="BUY",
            entry_price=Decimal("2400"),
            anchor=Decimal("2390"),
            reversal_confirmed=False,
        )
        assert blocked is False
        assert reason == "not_sell"

    def test_store_records_losing_sell_and_blocks(self) -> None:
        assert (
            record_losing_sell_close(
                symbol="XAUUSD",
                position_id=99,
                entry_price=Decimal("2395"),
                net_pnl=Decimal("-12"),
                direction="SELL",
                fully_closed=True,
            )
            == "created"
        )
        blocked, why = evaluate_durable_sell_cascade(
            symbol="XAUUSD",
            direction="SELL",
            entry_price=Decimal("2405"),
            reversal_confirmed=False,
        )
        assert blocked is True
        assert why == "SELL_CASCADE_UNRESOLVED_RALLY"
        # Independent BUY must not be blocked by SELL cascade.
        buy_blocked, buy_why = evaluate_durable_sell_cascade(
            symbol="XAUUSD",
            direction="BUY",
            entry_price=Decimal("2405"),
            reversal_confirmed=False,
        )
        assert buy_blocked is False
        assert buy_why == "not_sell"
