"""XAUUSD_I min-lot sizing — CASE A constraint vs calculation bug.

Uses live Weltrade-style specs (contract_size=100, volume_min=0.01,
tick_size=0.001, tick_value=0.1). Never fabricates fills or upsizes.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.services.signal_center_service import (
    _execution_classification,
    _row_from_score,
)
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.atr import stop_distance_from_atr
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile


# Live Weltrade XAUUSD_I (gateway /symbols/XAUUSD_I)
_VOLUME_MIN = Decimal("0.01")
_VOLUME_STEP = Decimal("0.01")
_CONTRACT = Decimal("100")
_TICK_SIZE = Decimal("0.001")
_TICK_VALUE = Decimal("0.1")
_EQUITY = Decimal("100.72")
_PRICE = Decimal("4380.013")


def _account(equity: Decimal = _EQUITY) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=equity,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=2000,
    )


@pytest.mark.unit
def test_xauusd_i_tick_and_contract_formulas_agree() -> None:
    dist = Decimal("9.8550")
    risk_amount = Decimal("1.01")
    raw_cs = risk_amount / (_CONTRACT * dist)
    raw_tv = risk_amount / ((dist / _TICK_SIZE) * _TICK_VALUE)
    assert abs(raw_cs - raw_tv) < Decimal("1e-18")
    assert raw_cs < _VOLUME_MIN


@pytest.mark.unit
def test_xauusd_i_volume_step_normalization() -> None:
    raw = Decimal("0.001024860476915271435819381025")
    normalized = raw.quantize(_VOLUME_STEP, rounding=ROUND_DOWN)
    assert normalized == Decimal("0.00")
    assert normalized < _VOLUME_MIN


@pytest.mark.unit
def test_xauusd_i_below_min_lot_is_legitimate_account_constraint() -> None:
    atr = (_PRICE * Decimal("0.0015")).quantize(Decimal("0.001"))
    dist = stop_distance_from_atr(atr)
    risk_pct = DEFAULT_ITE_CONFIG.risk_per_trade_pct
    risk_amount = (_EQUITY * risk_pct / Decimal("100")).quantize(Decimal("0.01"))
    raw = risk_amount / (_CONTRACT * dist)
    norm = raw.quantize(_VOLUME_STEP, rounding=ROUND_DOWN)
    min_loss = (_VOLUME_MIN * _CONTRACT * dist).quantize(Decimal("0.01"))
    needed = (min_loss / _EQUITY * Decimal("100")).quantize(Decimal("0.01"))
    profile = MicroAccountProfile()

    assert norm < _VOLUME_MIN
    assert needed > profile.hard_max_risk_pct
    # Safety must reject — never upsize to min_lot past hard_max.
    engine = RiskEngine()
    size = engine.size_position(
        equity=_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=dist,
        atr=atr,
        entry_price=_PRICE,
        contract_size=_CONTRACT,
        risk_per_trade_pct=risk_pct,
    )
    assert size.approved_lots == Decimal("0")
    assert size.capped is True
    # Dollar risk budget preserved (1% path), not inflated to min_lot loss.
    assert size.dollar_risk == risk_amount


@pytest.mark.unit
def test_xauusd_i_valid_volume_at_min_lot_when_stop_fits_hard_max() -> None:
    """Tight stop where min_lot risk <= 5% hard_max → micro conditional OK."""
    dist = Decimal("4.00")  # min_lot $ risk = 4.00 → ~3.97% of $100.72
    engine = RiskEngine()
    size = engine.size_position(
        equity=_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=dist,
        atr=None,
        entry_price=_PRICE,
        contract_size=_CONTRACT,
        risk_per_trade_pct=Decimal("1.0"),
    )
    assert size.approved_lots == _VOLUME_MIN
    assert size.capped is False
    min_loss = (_VOLUME_MIN * _CONTRACT * dist).quantize(Decimal("0.01"))
    assert size.dollar_risk == min_loss


@pytest.mark.unit
def test_risk_engine_labels_min_lot_constraint_not_missing_signal() -> None:
    atr = (_PRICE * Decimal("0.0015")).quantize(Decimal("0.001"))
    dist = stop_distance_from_atr(atr)
    engine = RiskEngine()
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="xau-min-lot-1",
            symbol="XAUUSD_I",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=dist,
            atr=atr,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=_PRICE,
        ),
        account=_account(),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    joined = " ".join(result.reasons)
    assert "MIN_LOT_CONSTRAINT" in joined
    assert "missing signal" not in joined.lower()


@pytest.mark.unit
def test_signal_center_min_lot_lifecycle_labels() -> None:
    cls = _execution_classification(
        direction="BUY",
        reject=True,
        reason="MIN_LOT_CONSTRAINT: calculated volume below broker volume_min",
        quality=94,
        confidence=83,
    )
    assert cls["signal_state"] == "VALID_SIGNAL"
    assert cls["execution_state"] == "EXECUTION_BLOCKED"
    assert cls["block_code"] == "MIN_LOT_CONSTRAINT"

    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "trade_quality": 94,
            "ai_confidence": 83,
            "reject": True,
            "reject_reason": (
                "MIN_LOT_CONSTRAINT: calculated volume below broker volume_min"
            ),
            "strategy_id": "momentum_scalping",
        }
    )
    assert row["signal_state"] == "VALID_SIGNAL"
    assert row["execution_state"] == "EXECUTION_BLOCKED"
    assert row["block_code"] == "MIN_LOT_CONSTRAINT"
    assert row["direction"] == "BUY"
    assert "BLOCKED" in row["badge"]
