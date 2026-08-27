"""Stale FVG is a per-setup veto, not a global sniper latch.

Does not send orders. Does not lower Opportunity 70, Sniper gates, Risk,
Safety, or OMS. Does not convert WAIT into TAKE.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.ai_scalping.config import scalping_ite_config
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.execution_chain_log import (
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.pipeline import scalp_ltf_zone_timeframes
from app.domain.market_data.timeframe import Timeframe
from tests.unit.test_xauusd_sniper_v2_lifecycle import (
    _bos,
    _dir,
    _fvg,
    _ob,
    _ready,
    _snap,
    _sniper,
    _struct,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _stale_fvg(*, side: str, high: str, low: str) -> MagicMock:
    gap = _fvg(side=side, high=high, low=low, freshness=90)
    gap.zone.formed_at = datetime.now(UTC) - timedelta(hours=20)
    return gap


def _m5_fvg(*, side: str, high: str, low: str) -> MagicMock:
    gap = _fvg(side=side, high=high, low=low, freshness=2)
    gap.timeframe = Timeframe.M5
    gap.zone.timeframe = Timeframe.M5
    return gap


def test_scalp_ltf_zone_timeframes_are_m5_m1() -> None:
    assert scalp_ltf_zone_timeframes(ITEConfig()) == ()
    tfs = scalp_ltf_zone_timeframes(scalping_ite_config())
    assert tfs == (Timeframe.M5, Timeframe.M1)


def test_stale_fvg_only_is_wait_stale_fvg() -> None:
    snap = _snap(fvgs=[_stale_fvg(side="BULLISH", high="2612", low="2608")])
    out = _sniper(snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65)
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason == "WAIT_STALE_FVG"
    assert out.diagnostics["setup_state"] == "STALE"
    assert out.pillars["fresh_zone"] is False


def test_stale_fvg_does_not_veto_fresh_ob_setup() -> None:
    snap = _snap(
        m5=_struct(bos=[_bos("UP")]),
        fvgs=[_stale_fvg(side="BULLISH", high="2620", low="2616")],
        obs=[_ob(bias="BUY")],
    )
    out = _sniper(
        snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65
    )
    assert out.passed is True
    assert out.action == "BUY"
    assert out.primary_reason is None
    assert out.diagnostics.get("zone_source") == "ob"
    assert "zone" in out.diagnostics["independent_evidence"]
    assert out.diagnostics.get("stale_zone_ignored") is True


def test_stale_fvg_does_not_veto_structure_plus_liquidity() -> None:
    snap = _snap(
        m5=_struct(bos=[_bos("DOWN")]),
        sweeps=[MagicMock(side="HIGH")],
        fvgs=[_stale_fvg(side="BEARISH", high="2616", low="2612")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL, buy=18, sell=82),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    assert out.passed is True
    assert out.action == "SELL"
    assert out.primary_reason is None
    assert "zone" not in out.diagnostics["independent_evidence"]
    assert "structure" in out.diagnostics["independent_evidence"]
    assert "liquidity" in out.diagnostics["independent_evidence"]


def test_fresh_m5_fvg_with_structure_can_take() -> None:
    snap = _snap(
        m1=_struct(bos=[_bos("UP")]),
        m5=_struct(bos=[_bos("UP")]),
    )
    snap.ltf_order_blocks = ()
    snap.ltf_fair_value_gaps = (
        MagicMock(active_gaps=[_m5_fvg(side="BULLISH", high="2612", low="2608")]),
    )
    out = _sniper(
        snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65
    )
    assert out.passed is True
    assert out.action == "BUY"
    assert out.diagnostics["setup_state"] == "TAKE"
    assert out.diagnostics.get("zone_source") == "fvg"
    assert out.diagnostics.get("zone_timeframe") == "M5"
    assert out.diagnostics["independent_evidence"].count("structure") == 1


def test_fresh_m5_ob_with_m1_retest_can_take() -> None:
    snap = _snap(
        m1=_struct(bos=[_bos("UP")]),
        m5=_struct(bos=[_bos("UP")]),
    )
    snap.ltf_order_blocks = (MagicMock(order_blocks=[_ob(bias="BUY")]),)
    snap.ltf_fair_value_gaps = ()
    out = _sniper(
        snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65
    )
    assert out.passed is True
    assert out.action == "BUY"
    assert "zone" in out.diagnostics["independent_evidence"]
    assert out.diagnostics.get("zone_source") == "ob"
    assert out.diagnostics.get("entry_state") in {"RETEST", "INSIDE", "CONTROLLED"}


def test_previous_cycle_stale_fvg_cannot_poison_current_cycle() -> None:
    first = _sniper(
        _snap(fvgs=[_stale_fvg(side="BULLISH", high="2612", low="2608")]),
        _dir(TradeDirection.BUY),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    assert first.primary_reason == "WAIT_STALE_FVG"
    second = _sniper(
        _snap(
            m5=_struct(bos=[_bos("UP")]),
            fvgs=[_fvg(side="BULLISH", high="2612", low="2608", freshness=2)],
        ),
        _dir(TradeDirection.BUY),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    assert second.passed is True
    assert second.action == "BUY"
    assert second.diagnostics["setup_state"] == "TAKE"


def test_wait_stale_fvg_does_not_enter_risk() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "opportunity_score": 70,
            "opportunity_threshold": 70,
            "reject": True,
            "reject_reason": "WAIT_STALE_FVG",
            "sniper_entry": {
                "passed": False,
                "action": "WAIT",
                "setup_state": "STALE",
                "primary_reason": "WAIT_STALE_FVG",
            },
        }
    )
    assert row["pipeline"]["sniper"] == "WAIT"
    assert row["pipeline"]["risk"] == "NOT_REACHED"
    assert row["pipeline"]["safety"] == "NOT_REACHED"
    assert row["pipeline"]["optimizer"] == "NOT_REACHED"
    assert row["pipeline"]["oms"] == "NOT_REACHED"
    handoff = build_execution_handoff(
        take=False, forwarded_to_oms=False, abort_reason="WAIT_STALE_FVG"
    )
    assert handoff["risk_entered"] is False
    assert handoff["oms_entered"] is False
    assert handoff["execution_confirmed"] is False


def test_genuine_take_enters_risk() -> None:
    handoff = build_execution_handoff(take=True, forwarded_to_oms=False)
    assert handoff["decision_take"] is True
    assert handoff["risk_entered"] is True
    assert handoff["oms_entered"] is False
    assert handoff["execution_confirmed"] is False


def test_risk_and_safety_pass_can_reach_optimizer_oms() -> None:
    out = evaluate_gold_execution_contract(_ready())
    assert out.may_submit_oms is True
    handoff = build_execution_handoff(take=True, forwarded_to_oms=True, mt5_ticket=None)
    assert handoff["risk_entered"] is True
    assert handoff["safety_entered"] is True
    assert handoff["optimizer_entered"] is True
    assert handoff["oms_entered"] is True
    assert handoff["execution_confirmed"] is False


def test_oms_entered_only_after_actual_oms_invocation() -> None:
    before = build_execution_handoff(take=True, forwarded_to_oms=False)
    assert before["oms_entered"] is False
    after = build_execution_handoff(take=True, forwarded_to_oms=True, mt5_ticket=None)
    assert after["oms_entered"] is True
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "BUY",
                "signal_action": "BUY",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
            }
        ),
        {"forwarded_to_oms": False, "mt5_ticket": None, "take": True},
    )
    assert over["pipeline"]["oms"] != "BLOCK"


def test_executed_requires_forwarded_to_oms_and_real_ticket() -> None:
    take_only = build_execution_handoff(take=True, forwarded_to_oms=False)
    assert take_only["execution_confirmed"] is False
    forwarded = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=None
    )
    assert forwarded["execution_confirmed"] is False
    filled = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=424242
    )
    assert filled["execution_confirmed"] is True
    assert filled["oms_entered"] is True


def test_sniper_take_is_not_an_order_or_ticket() -> None:
    snap = _snap(
        m5=_struct(bos=[_bos("UP")]),
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY))
    assert out.passed is True
    assert out.diagnostics.get("mt5_ticket") is None
    assert out.diagnostics.get("forwarded_to_oms") in {None, False}
    assert "order_send" not in repr(out)
