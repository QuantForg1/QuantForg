"""Directional scalping: BUY and SELL share one cycle. No BUY-only lock."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.ai_scalping_mode import apply_trading_mode_to_runtime
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.auto_trading import AutoTradePolicy
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    consume_immediate_wakeup,
    note_opportunity_change,
    reset_decision_cycle,
)
from app.domain.institutional_trading.operations.position_plan import (
    build_position_plan,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
    evaluate_opportunity,
)
from app.domain.institutional_trading.operations.trade_classifier import (
    TradeClass,
    classify_trade,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
_APP = ROOT / "app"


def test_buy_only_mode_is_not_a_production_config() -> None:
    hits: list[str] = []
    for path in _APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in (
            "BUY_ONLY_MODE",
            "LONG_ONLY_MODE",
            "SELL_ENABLED",
            "allow_sell = False",
        ):
            if needle in text:
                hits.append(f"{path.relative_to(ROOT)}:{needle}")
    assert hits == []
    assert DEFAULT_AI_SCALPING_CONFIG.never_prefer_buy_only is True


def test_operator_defaults_are_scalping_not_swing() -> None:
    assert AutoTradePolicy().trading_mode == "scalping"
    assert OperationsControlPlane().trading_mode == "scalping"
    assert DEFAULT_ITE_CONFIG.trading_mode == "swing"
    assert ITEConfig().is_scalping() is False
    assert DEFAULT_AI_SCALPING_CONFIG.never_prefer_buy_only is True


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_score_70_with_direction_is_scalp_candidate(side: str) -> None:
    classified = classify_trade(
        opportunity_score=70,
        direction=side,
        structure=60,
        confidence=70,
    )
    assert classified.trade_class is TradeClass.SCALP
    assert classified.direction == side
    verdict = evaluate_opportunity(
        direction=side,
        structure=80,
        momentum=80,
        quality=82,
        confidence=81,
        regime="trend",
        price_action=80,
        liquidity=80,
        volatility=80,
        execution_quality=80,
        mtf_alignment=80,
        risk_reward=1.4,
    )
    assert verdict.opportunity_score >= OPPORTUNITY_SCORE_THRESHOLD
    assert verdict.direction == side
    assert verdict.eligible is True


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_score_85_with_holding_evidence_is_hold(side: str) -> None:
    classified = classify_trade(
        opportunity_score=STRONG_CANDIDATE_THRESHOLD,
        direction=side,
        structure=72,
        regime="trend",
        risk_reward=1.4,
        confidence=86,
    )
    assert classified.trade_class is TradeClass.HOLD
    assert classified.direction == side


def test_direction_none_does_not_trade_even_at_score_90() -> None:
    verdict = evaluate_opportunity(
        direction="NONE",
        structure=80,
        momentum=80,
        quality=90,
        confidence=90,
        regime="trend",
        price_action=80,
        liquidity=80,
        volatility=80,
        execution_quality=80,
        mtf_alignment=80,
        risk_reward=1.5,
    )
    assert verdict.eligible is False
    assert verdict.fault_code == "DIRECTION_NONE"
    classified = classify_trade(opportunity_score=90, direction="NONE")
    assert classified.trade_class is TradeClass.NO_TRADE


def test_existing_buy_does_not_globally_forbid_sell() -> None:
    out = may_add_scalping_trade(
        open_positions=1,
        max_open=10,
        new_confidence=70,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("BUY",),
        require_improvement=True,
        require_unrealized_profit=True,
        same_direction_profits=(Decimal("-1.00"),),
        open_profits=(Decimal("-1.00"),),
    )
    assert out.allow is True
    assert "Opposite direction" in out.reason


def test_existing_sell_does_not_globally_forbid_buy() -> None:
    out = may_add_scalping_trade(
        open_positions=2,
        max_open=10,
        new_confidence=71,
        best_open_confidence=90,
        new_direction="BUY",
        open_directions=("SELL",),
        require_improvement=True,
    )
    assert out.allow is True
    assert "Opposite direction" in out.reason


def test_same_side_add_on_still_requires_improvement() -> None:
    blocked = may_add_scalping_trade(
        open_positions=1,
        max_open=10,
        new_confidence=70,
        best_open_confidence=70,
        new_direction="BUY",
        open_directions=("BUY",),
        require_improvement=True,
        min_confidence_delta=3,
    )
    assert blocked.allow is False


def test_direction_change_wakes_a_new_decision_cycle() -> None:
    reset_decision_cycle()
    note_opportunity_change(score=72, direction="BUY", trade_class="SCALP")
    assert consume_immediate_wakeup() is None
    note_opportunity_change(score=74, direction="SELL", trade_class="SCALP")
    assert consume_immediate_wakeup() == "direction_change"
    reset_decision_cycle()


def test_current_snapshot_direction_is_not_stale_buy() -> None:
    buy = evaluate_opportunity(
        direction="BUY",
        structure=70,
        momentum=70,
        quality=72,
        confidence=71,
    )
    sell = evaluate_opportunity(
        direction="SELL",
        structure=70,
        momentum=70,
        quality=72,
        confidence=71,
    )
    assert buy.direction == "BUY"
    assert sell.direction == "SELL"
    assert buy.eligible is sell.eligible


def test_scalp_plan_can_target_multiple_risk_constrained_legs() -> None:
    classified = classify_trade(opportunity_score=83, direction="SELL", structure=62)
    assert classified.trade_class is TradeClass.SCALP
    plan = build_position_plan(
        cycle_id="cycle-dir-1",
        snapshot_id="snap-dir-1",
        symbol="XAUUSD_i",
        direction="SELL",
        trade_class=classified.trade_class,
        opportunity_score=83,
        confidence=80,
        aggregate_lots=Decimal("0.04"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash="h-dir",
        risk_allowed_count=4,
    )
    assert plan.effective_count == 4
    assert plan.target_count >= plan.effective_count
    assert plan.cycle_id == "cycle-dir-1"
    assert plan.snapshot_id == "snap-dir-1"
    assert plan.position_plan_id
    assert len(plan.legs) == plan.effective_count
    keys = [leg.idempotency_key for leg in plan.legs]
    assert len(set(keys)) == len(keys)


def test_empty_trading_mode_applies_scalping() -> None:
    from types import SimpleNamespace

    runtime = SimpleNamespace(
        decision_pipeline=SimpleNamespace(
            config=DEFAULT_ITE_CONFIG,
            risk_engine=None,
        ),
        position_management=SimpleNamespace(
            engine=SimpleNamespace(config=None),
        ),
        plane=SimpleNamespace(max_open_trades=1, trading_mode="swing"),
    )
    out = apply_trading_mode_to_runtime(runtime, mode="")
    assert out["trading_mode"] == "scalping"
    assert runtime.decision_pipeline.config.is_scalping() is True
    assert runtime.plane.trading_mode == "scalping"


def test_hard_risk_safety_and_leverage_unchanged() -> None:
    src = (_APP / "domain" / "trading" / "xauusd_specs.py").read_text(
        encoding="utf-8"
    )
    assert 'MAX_LEVERAGE = Decimal("2000")' in src
    assert Decimal("2000") == MAX_LEVERAGE
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert STRONG_CANDIDATE_THRESHOLD == 85
    adapter = (
        _APP / "application" / "services" / "institutional_oms_adapter.py"
    ).read_text(encoding="utf-8")
    assert "def submit_market(" in adapter
    guard = (
        _APP / "domain" / "institutional_trading" / "ai_scalping" / "duplicate_guard.py"
    ).read_text(encoding="utf-8")
    assert "FORCE_FIRST_TRADE" not in guard
    assert Decimal("2000") == MAX_LEVERAGE
