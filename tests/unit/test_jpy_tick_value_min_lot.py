"""JPY min-lot must use broker tick value, not gold lots×CS×stop identity.

Live 2026-09-07 EURJPY/USDJPY cycles rejected MIN_LOT_EXCEEDS_RISK_BUDGET at
needed_pct≈105% because 0.01 * 100000 * 0.108 was treated as $108 USD.
Does not lower P>70, Sniper, RR, $6/$20/$30, or force trades.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.domain.entities.mt5_market import MT5SymbolInfo
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CLASS_FEASIBLE,
    CLASS_INFEASIBLE,
    evaluate_min_lot_feasibility,
    evaluate_setup_tradeability,
    lot_dollar_risk,
    min_lot_needed_pct,
)
from app.infrastructure.brokers.mt5.gateway_client import _positive_tick
from tests.unit.test_autonomous_gold_execution import _ready

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

# Live Railway cycle 2026-09-07T10:04Z USDJPY
_EQUITY = Decimal("102.7")
_STOP = Decimal("0.1082250015")
_MIN = Decimal("0.01")
_CS = Decimal("100000")
_HARD = MicroAccountProfile().hard_max_risk_pct
_TICK_SIZE = Decimal("0.001")
_TICK_VALUE = Decimal("0.68")  # USD per tick per 1.00 lot (Weltrade-style)


def test_live_usdjpy_identity_formula_matches_production_false_reject() -> None:
    """Reproduction: lots×CS×stop treats yen as dollars → ~105% of equity."""
    needed = min_lot_needed_pct(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
    )
    assert needed == Decimal("105.38")
    result = evaluate_min_lot_feasibility(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
        hard_max_risk_pct=_HARD,
    )
    assert result.classification == CLASS_INFEASIBLE
    assert result.skip_expensive_downstream is True


def test_live_usdjpy_tick_value_is_feasible_under_hard_max() -> None:
    usd = lot_dollar_risk(
        _MIN,
        stop_distance=_STOP,
        contract_size=_CS,
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )
    assert usd < Decimal("6.00")
    result = evaluate_min_lot_feasibility(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
        hard_max_risk_pct=_HARD,
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )
    assert result.classification == CLASS_FEASIBLE
    assert result.infeasible is False
    assert result.skip_expensive_downstream is False
    assert result.needed_pct is not None
    assert result.needed_pct < _HARD
    assert result.stop_changed is False
    assert result.lot_changed is False


def test_setup_tradeability_forwards_ticks_into_feasibility() -> None:
    identity = evaluate_setup_tradeability(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
    )
    ticked = evaluate_setup_tradeability(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )
    assert identity.feasibility.infeasible is True
    assert ticked.feasibility.infeasible is False
    assert ticked.estimated_risk_at_min_lot == lot_dollar_risk(
        _MIN,
        stop_distance=_STOP,
        contract_size=_CS,
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )


def test_pipeline_gate_uses_live_ticks() -> None:
    pipe = InstitutionalDecisionPipeline(config=ITEConfig())
    blocked = pipe.evaluate_min_lot_feasibility_gate(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
    )
    allowed = pipe.evaluate_min_lot_feasibility_gate(
        stop_distance=_STOP,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )
    assert blocked.skip_expensive_downstream is True
    assert allowed.skip_expensive_downstream is False
    assert allowed.classification == CLASS_FEASIBLE


def test_mt5_symbol_info_exposes_tick_aliases() -> None:
    info = MT5SymbolInfo(
        code="USDJPY",
        tick_size=_TICK_SIZE,
        tick_value=_TICK_VALUE,
    )
    assert info.tick_size == _TICK_SIZE
    assert info.tick_value == _TICK_VALUE
    assert info.trade_tick_size == _TICK_SIZE
    assert info.trade_tick_value == _TICK_VALUE
    payload = info.to_dict()
    assert payload["tick_size"] == "0.001"
    assert payload["tick_value"] == "0.68"


def test_positive_tick_parser_drops_zero() -> None:
    assert _positive_tick("0.001") == Decimal("0.001")
    assert _positive_tick("0") is None
    assert _positive_tick(None) is None
    assert _positive_tick("") is None


def test_non_gold_min_lot_rotates_universe() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            symbol="USDJPY",
            gold_only=False,
            direction="SELL",
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=(
                "MIN_LOT_INFEASIBLE",
                "MIN_LOT_EXCEEDS_RISK_BUDGET",
            ),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "MIN_LOT_EXCEEDS_RISK_BUDGET"
    assert out.decision_state == DecisionState.CANDIDATE_BLOCK.value
    assert out.next_action == CandidateAction.ROTATE_FOCUS.value


def test_gold_min_lot_still_waits_same_focus() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            min_lot_infeasible=True,
            risk_eligible=False,
            approved_lots=Decimal("0"),
            action="NO_TRADE",
            risk_reasons=("MIN_LOT_CONSTRAINT: strategy-approved stop exceeds max",),
        )
    )
    assert out.next_action == CandidateAction.WAIT_SAME_FOCUS.value
    assert out.may_submit_oms is False
