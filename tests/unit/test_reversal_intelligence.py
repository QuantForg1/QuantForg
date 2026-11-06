"""Reversal intelligence + close-then-reverse — shadow-safe unit coverage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.services.institutional_ite_runtime import _shadow_reversal_kwargs
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.management.close_then_reverse import (
    evaluate_close_then_reverse,
)
from app.domain.institutional_trading.management.exit_context import (
    propose_reversal_exit,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


class TestReversalClassification:
    def test_genuine_bearish_reversal_against_buy(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            choch_against=True,
            htf_agrees_against=True,
        )
        assert p.structure_broken is True
        assert p.is_retracement is False
        assert p.classification == "htf_trend_reversal"

    def test_temporary_m1_pullback(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            ltf_only_noise=True,
            bos_against=False,
            choch_against=False,
        )
        assert p.is_retracement is True
        assert p.structure_broken is False
        assert p.classification == "temporary_m1_pullback"

    def test_false_m1_reversal_without_htf(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            choch_against=False,
            htf_agrees_against=False,
        )
        assert p.structure_broken is False
        assert p.classification == "false_reversal_noise"

    def test_conflicting_timeframes(self) -> None:
        p = propose_reversal_exit(
            position_side="sell",
            bos_against=True,
            htf_agrees_against=False,
        )
        assert p.structure_broken is False
        assert p.trend_reversed is False

    def test_stale_market_data(self) -> None:
        p = propose_reversal_exit(
            position_side="sell",
            bos_against=True,
            htf_agrees_against=True,
            data_age_seconds=999,
        )
        assert p.stale_data is True
        assert p.structure_broken is False

    def test_spread_spike_defers(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            htf_agrees_against=True,
            spread=9.0,
            emergency_spread=5.0,
        )
        assert p.structure_broken is False
        assert "spread" in p.reason


class TestCloseThenReverseGates:
    def _confirmed(self):
        return propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            choch_against=True,
            htf_agrees_against=True,
        )

    def test_shadow_observe_does_not_submit(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=True,
            live_reversal_enabled=False,
            live_reverse_entry_enabled=False,
        )
        assert plan.stage == "observe"
        assert plan.submit_close is False
        assert plan.submit_opposite is False

    def test_unconfirmed_close_blocks_opposite(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=True,
            close_request_sent=True,
            close_broker_confirmed=False,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=True,
            opposite_eligible=True,
        )
        assert plan.submit_opposite is False
        assert plan.stage == "await_broker_confirm"

    def test_failed_close_blocks_opposite(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=True,
            close_rejected=True,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=True,
            opposite_eligible=True,
        )
        assert plan.submit_opposite is False
        assert plan.stage == "reject"

    def test_broker_confirmed_close_then_opposite_shadow_only(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=False,
            close_broker_confirmed=True,
            opposite_eligible=True,
            concurrent_positions=0,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=False,
        )
        assert plan.stage == "evaluate_opposite"
        assert plan.submit_opposite is False
        assert "shadow" in plan.reason

    def test_never_reverse_to_recover_loss(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=True,
            loss_recovery_motive=True,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=True,
        )
        assert plan.allowed is False
        assert plan.submit_close is False
        assert plan.submit_opposite is False

    def test_pullback_never_requests_close(self) -> None:
        pullback = propose_reversal_exit(
            position_side="buy",
            ltf_only_noise=True,
        )
        plan = evaluate_close_then_reverse(
            proposal=pullback,
            position_open_broker=True,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=True,
        )
        assert plan.submit_close is False
        assert plan.stage == "observe"

    def test_duplicate_flip_blocked_by_cooldown(self) -> None:
        plan = evaluate_close_then_reverse(
            proposal=self._confirmed(),
            position_open_broker=False,
            close_broker_confirmed=True,
            opposite_eligible=True,
            concurrent_positions=0,
            reverse_cooldown_active=True,
            live_reversal_enabled=True,
            live_reverse_entry_enabled=True,
        )
        assert plan.submit_opposite is False
        assert plan.reason == "reverse_cooldown_active"


class TestSideAwareShadowKwargs:
    def test_same_side_bos_does_not_flag_against(self) -> None:
        """BUY position + bullish BOS must not invent a bearish reversal."""
        bullish_bos = SimpleNamespace(
            kind="BOS",
            trend_direction="UP",
            previous_trend=None,
        )
        structure = SimpleNamespace(
            breaks_of_structure=[bullish_bos],
            changes_of_character=[],
        )
        snapshot = SimpleNamespace(
            structure_by_tf={"M5": structure, "M15": structure},
            primary_structure=structure,
            as_of=None,
            ai_score=None,
            score_breakdown={"bos": 85, "choch": 20, "mtf": 80, "momentum": 60},
        )
        pos = SimpleNamespace(side="buy", ai_entry_confidence=70)
        pctx = SimpleNamespace(spread=0.25, ai_current_confidence=68)
        kwargs = _shadow_reversal_kwargs(snapshot, pos, pctx)
        assert kwargs["bos_against"] is False
        assert kwargs["choch_against"] is False

    def test_opposing_choch_flags_against(self) -> None:
        """BUY position + CHOCH from prior UP → bearish against."""
        choch = SimpleNamespace(
            kind="CHOCH",
            previous_trend="UP",
            trend_direction=None,
        )
        structure = SimpleNamespace(
            breaks_of_structure=[],
            changes_of_character=[choch],
        )
        snapshot = SimpleNamespace(
            structure_by_tf={"M5": structure, "M15": structure},
            primary_structure=structure,
            as_of=None,
            ai_score=None,
            score_breakdown={},
            trend=SimpleNamespace(trade_bias=None),
        )
        # Minimal decide_scalping_direction needs more fields — patch via
        # structure_tfs alone is enough for choch_against.
        pos = SimpleNamespace(side="buy", ai_entry_confidence=70)
        pctx = SimpleNamespace(spread=0.25, ai_current_confidence=40)
        kwargs = _shadow_reversal_kwargs(snapshot, pos, pctx)
        assert kwargs["choch_against"] is True
        assert kwargs["bos_against"] is False
        # Mapped side sanity for CHOCH previous UP → SELL
        from app.domain.institutional_trading.ai_scalping.direction import (
            structure_event_side,
        )

        assert structure_event_side(choch) is TradeDirection.SELL
