"""Decision-state consistency + live min-lot / ATR-stop audit.

Preserves BUY/SELL through Risk and Safety blockers. Does not upsize,
tighten stops, or send orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    DecisionAction,
    EligibilityResult,
    TradeDirection,
)
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    classify_candidate_outcome,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
    facts_from_cycle,
)
from app.domain.institutional_trading.operations.position_plan import (
    HOLD_MAX_OPEN_TRADES,
    SCALP_MAX_OPEN_TRADES,
    build_position_plan,
    remaining_quantforg_capacity,
    strategy_target_count,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    OWNER_MANUAL,
    QUANTFORG_MAGIC,
    classify_position_owner,
    is_quantforg_owned_position,
    same_symbol_ownership_facts,
)
from app.domain.institutional_trading.operations.trade_classifier import TradeClass
from app.domain.institutional_trading.session_policy import TRADABLE_SESSIONS_24_7
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    canonical_gold_execution_symbol,
    is_bare_gold_symbol,
)
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN
from tests.unit.test_autonomous_gold_execution import _ready
from tests.unit.test_institutional_trading_phase_b import _account, _snapshot

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_LIVE_EQUITY = Decimal("160.55")
_LIVE_ATR = Decimal("8.2257")
_SCALP_STOP_MULT = Decimal("1.10")
_LIVE_STOP = (_LIVE_ATR * _SCALP_STOP_MULT).quantize(Decimal("0.0001"))
_MIN_LOT_REASON = (
    "MIN_LOT_CONSTRAINT: calculated volume below broker volume_min "
    "(no upsize to min_lot)"
)


def _confluence(direction: TradeDirection, confidence: int = 82) -> ConfluenceResult:
    return ConfluenceResult(
        confidence=confidence,
        direction=direction,
        reasons=("trend_continuation",),
        rejected_rules=(),
        input_hash="decision-state-hash",
        band="tradable",
        passed=direction is not TradeDirection.NONE,
        factors={"quality": 92},
    )


def _blocked_elig(*reasons: str) -> EligibilityResult:
    return EligibilityResult(
        eligible=False,
        checks={"risk_available": False, "session_valid": True},
        rejection_reasons=reasons or (_MIN_LOT_REASON,),
    )


def _open_elig() -> EligibilityResult:
    return EligibilityResult(
        eligible=True,
        checks={"risk_available": True, "session_valid": True},
        rejection_reasons=(),
    )


def test_buy_min_lot_constraint_keeps_buy() -> None:
    decision = TradeDecisionEngine(config=ITEConfig()).decide(
        snapshot=_snapshot(quality=92),
        confluence=_confluence(TradeDirection.BUY),
        eligibility=_blocked_elig(_MIN_LOT_REASON),
        account=_account(),
        risk_score=40,
        risk_reasons=(_MIN_LOT_REASON,),
        approved_lots=Decimal("0"),
    )
    assert decision.action is DecisionAction.NO_TRADE
    assert decision.direction is TradeDirection.BUY


def test_sell_min_lot_constraint_keeps_sell() -> None:
    decision = TradeDecisionEngine(config=ITEConfig()).decide(
        snapshot=_snapshot(quality=92),
        confluence=_confluence(TradeDirection.SELL),
        eligibility=_blocked_elig(_MIN_LOT_REASON),
        account=_account(),
        risk_score=40,
        risk_reasons=(_MIN_LOT_REASON,),
        approved_lots=Decimal("0"),
    )
    assert decision.action is DecisionAction.NO_TRADE
    assert decision.direction is TradeDirection.SELL


def test_genuine_direction_none_stays_none() -> None:
    decision = TradeDecisionEngine(config=ITEConfig()).decide(
        snapshot=_snapshot(quality=92),
        confluence=_confluence(TradeDirection.NONE, confidence=40),
        eligibility=_open_elig(),
        account=_account(),
        risk_score=10,
    )
    assert decision.action is DecisionAction.NO_TRADE
    assert decision.direction is TradeDirection.NONE


def test_contract_buy_risk_min_lot_keeps_buy_and_risk_gate() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="BUY",
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=(_MIN_LOT_REASON,),
        )
    )
    assert out.may_submit_oms is False
    assert out.direction == "BUY"
    assert out.fault_code == "MIN_LOT_CONSTRAINT"
    assert out.blocking_stage == "RISK"
    assert out.decision_state == DecisionState.CANDIDATE_BLOCK.value
    assert out.decision_state != DecisionState.NO_EXECUTABLE_FOCUS.value
    assert out.fault_code != "DIRECTION_NONE"


def test_contract_sell_risk_min_lot_keeps_sell() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="SELL",
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=False,
            risk_reasons=(_MIN_LOT_REASON,),
        )
    )
    assert out.direction == "SELL"
    assert out.fault_code == "MIN_LOT_CONSTRAINT"
    assert out.blocking_stage == "RISK"
    assert out.may_submit_oms is False


def test_contract_buy_safety_block_keeps_buy() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="BUY",
            action="NO_TRADE",
            safety_allowed=False,
            safety_reasons=("SAFETY_BLOCKED: exposure",),
        )
    )
    assert out.direction == "BUY"
    assert out.blocking_stage == "SAFETY"
    assert out.fault_code == "SAFETY_BLOCKED"
    assert out.fault_code != "DIRECTION_NONE"
    assert out.may_submit_oms is False


def test_contract_sell_safety_block_keeps_sell() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="SELL",
            action="SELL",
            safety_allowed=False,
            safety_reasons=("SAFETY_BLOCKED: kill path",),
        )
    )
    assert out.direction == "SELL"
    assert out.blocking_stage == "SAFETY"
    assert out.fault_code == "SAFETY_BLOCKED"


def test_contract_genuine_none_is_direction_none() -> None:
    out = evaluate_gold_execution_contract(
        _ready(direction="NONE", action="NO_TRADE")
    )
    assert out.direction == "NONE"
    assert out.fault_code == "DIRECTION_NONE"
    assert out.blocking_stage == "DECISION"
    assert out.may_submit_oms is False


def test_execution_contract_does_not_rewrite_risk_into_none() -> None:
    facts = facts_from_cycle(
        snapshot=SimpleNamespace(symbol="XAUUSD_i", spread=Decimal("0.20")),
        account=SimpleNamespace(
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            leverage=Decimal("2000"),
            market_open=True,
        ),
        decision=SimpleNamespace(
            symbol="XAUUSD_i",
            direction=TradeDirection.BUY,
            action=DecisionAction.NO_TRADE,
            quality=92,
            confidence=82,
            eligibility=EligibilityResult(
                eligible=False,
                checks={"risk_available": False},
                rejection_reasons=("Risk engine rejected",),
            ),
            risk_reasons=(_MIN_LOT_REASON,),
            approved_lots=Decimal("0"),
            estimated_rr=Decimal("1.20"),
            confluence=SimpleNamespace(factors={"structure_score": 70}),
        ),
        optimizer={"final_state": "EXECUTE_NOW"},
        execution_enabled=True,
        force_shadow=False,
        gateway_connected=True,
        broker_connected=True,
        symbol_tradable=True,
        auto_running=True,
        kill_switch=False,
        oms_orders_allowed=True,
        safety_allowed=True,
        last_ai_score={"opportunity_score": 82, "opportunity_threshold": 70},
    )
    assert facts.direction == "BUY"
    assert facts.min_lot_infeasible is True
    out = evaluate_gold_execution_contract(facts)
    assert out.direction == "BUY"
    assert out.fault_code == "MIN_LOT_CONSTRAINT"
    assert out.blocking_stage == "RISK"
    assert out.decision_state == DecisionState.CANDIDATE_BLOCK.value


def test_classify_min_lot_abort_is_risk_not_direction_none() -> None:
    out = classify_candidate_outcome(
        abort_reason="MIN_LOT_CONSTRAINT",
        failed_reasons=(_MIN_LOT_REASON,),
        cycle_outcome="execution_contract",
        decision_action="NO_TRADE",
    )
    assert out["fault_code"] == "MIN_LOT_CONSTRAINT"
    assert out["blocking_stage"] == "RISK"
    assert out["decision_state"] == DecisionState.CANDIDATE_BLOCK.value
    assert out["fault_code"] != "DIRECTION_NONE"
    assert out["next_action"] != CandidateAction.NO_EXECUTABLE_FOCUS.value


def test_live_min_lot_risk_math_is_5_64_and_rejects() -> None:
    min_loss = (VOLUME_MIN * CONTRACT_SIZE * _LIVE_STOP).quantize(Decimal("0.0001"))
    needed = (min_loss / _LIVE_EQUITY * Decimal("100")).quantize(Decimal("0.01"))
    profile = MicroAccountProfile()
    assert Decimal("0.01") == VOLUME_MIN
    assert profile.hard_max_risk_pct == Decimal("80.0")
    assert needed == Decimal("5.64")
    assert needed < profile.hard_max_risk_pct

    engine = RiskEngine()
    size = engine.size_position(
        equity=_LIVE_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=_LIVE_STOP,
        atr=_LIVE_ATR,
        entry_price=Decimal("2400"),
        contract_size=CONTRACT_SIZE,
        risk_per_trade_pct=Decimal("1.0"),
    )
    assert size.approved_lots == Decimal("0")
    assert size.block_reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"

    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="live-min-lot-160",
            symbol="XAUUSD_I",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=_LIVE_STOP,
            atr=_LIVE_ATR,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=Decimal("2400"),
        ),
        account=AccountSnapshot(
            login=1,
            balance=_LIVE_EQUITY,
            equity=_LIVE_EQUITY,
            margin=Decimal("0"),
            free_margin=_LIVE_EQUITY,
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=2000,
        ),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    assert "MIN_LOT_EXCEEDS_RISK_BUDGET" in " ".join(result.reasons)


def test_hard_max_and_min_lot_unchanged() -> None:
    assert MicroAccountProfile().hard_max_risk_pct == Decimal("80.0")
    assert Decimal("0.01") == VOLUME_MIN
    assert RiskEngine().config.min_lot == Decimal("0.01")
    assert RiskEngine().config.max_risk_per_trade_pct == Decimal("1")


def test_invalid_upward_normalization_rejected() -> None:
    raw = Decimal("0.007")
    engine = RiskEngine()
    size = engine.size_position(
        equity=_LIVE_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=raw,
        stop_distance=_LIVE_STOP,
        atr=_LIVE_ATR,
        entry_price=Decimal("2400"),
        contract_size=CONTRACT_SIZE,
        risk_per_trade_pct=Decimal("1.0"),
    )
    assert size.approved_lots == Decimal("0")
    assert size.block_reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_scalp_atr_stop_provenance_unchanged() -> None:
    pipeline = (
        Path(__file__).resolve().parents[2]
        / "app/application/services/institutional_decision_pipeline.py"
    ).read_text(encoding="utf-8")
    assert 'stop_mult = Decimal("1.10") if cfg.is_scalping() else Decimal("1.5")' in pipeline
    assert DEFAULT_AI_SCALPING_CONFIG.stop_atr_mult == Decimal("1.10")
    assert Decimal("9.0483") == _LIVE_STOP
    assert ITEConfig(trading_mode="scalping").is_scalping() is True


def test_multiposition_caps_and_min_stack_unchanged() -> None:
    assert 2 <= strategy_target_count(
        trade_class=TradeClass.SCALP, opportunity_score=82
    ) <= SCALP_MAX_OPEN_TRADES
    assert 1 <= strategy_target_count(
        trade_class=TradeClass.HOLD, opportunity_score=86
    ) <= HOLD_MAX_OPEN_TRADES
    scalp = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=10,
        portfolio_allowed_count=10,
        broker_allowed_count=10,
        min_lot=Decimal("0.01"),
    )
    hold = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.HOLD,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=5, trading_mode="swing"),
        risk_allowed_count=5,
        portfolio_allowed_count=5,
        broker_allowed_count=5,
        min_lot=Decimal("0.01"),
    )
    constrained = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=2,
        portfolio_allowed_count=8,
        broker_allowed_count=7,
        min_lot=Decimal("0.01"),
    )
    assert scalp.effective_count == SCALP_MAX_OPEN_TRADES
    assert hold.effective_count == HOLD_MAX_OPEN_TRADES
    assert constrained.effective_count == 2
    assert constrained.aggregate_lots == Decimal("0.02") or constrained.per_position_lots > 0


def test_gold_manual_and_session_regressions() -> None:
    assert canonical_gold_execution_symbol() == CANONICAL_GOLD_BROKER_DISPLAY
    assert is_bare_gold_symbol("XAUUSD") is True
    assert QUANTFORG_MAGIC == 260720
    manual = SimpleNamespace(magic=0, symbol="XAUUSD_i", comment="ite:v1")
    owned = SimpleNamespace(magic=QUANTFORG_MAGIC, symbol="XAUUSD_i", comment="ite:v1")
    assert is_quantforg_owned_position(manual) is False
    assert classify_position_owner(manual) == OWNER_MANUAL
    assert is_quantforg_owned_position(owned) is True
    facts = same_symbol_ownership_facts(
        [manual, manual, manual, manual],
        candidate_symbol="XAUUSD_i",
    )
    assert facts["quantforg_open_count"] == 0
    assert facts["manual_same_symbol_count"] == 4
    assert facts["already_open"] is False
    assert facts["already_open_reason"] == "MANUAL_SAME_SYMBOL_PRESENT"
    assert facts["candidate_allowed"] is True
    assert remaining_quantforg_capacity(
        current_count=0,
        configured_max=10,
        class_cap=10,
    ) == 10
    assert any(s.value for s in TRADABLE_SESSIONS_24_7)
