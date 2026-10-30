"""Per-trade planned-risk cap is 14% of LIVE equity only.

The static $7.00 (14% of the $50 reference capital) is replaced by 14% of
live equity. A stricter configured dollar cap still wins.
"""

from __future__ import annotations

from decimal import Decimal as D
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.config import MAX_PLANNED_SL_RISK_USD

pytestmark = pytest.mark.unit


def _evaluate(equity: str, stop: str, config: RiskEngineConfig | None = None):
    eq = D(equity)
    engine = RiskEngine(
        config=config
        or RiskEngineConfig(
            min_lot=D("0.01"),
            lot_step=D("0.01"),
            max_lot=D("0.01"),
            contract_size=D("100"),
        )
    )
    return engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id=f"cap-{equity}-{stop}",
            symbol="XAUUSD",
            side="sell",
            requested_lots=D("0.01"),
            stop_loss_distance=D(stop),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=D("4028.85"),
            contract_size=D("100"),
        ),
        account=AccountSnapshot(
            login=1,
            balance=eq,
            equity=eq,
            margin=D("0"),
            free_margin=eq,
            margin_level=D("0"),
            profit=D("0"),
            leverage=2000,
        ),
        positions=[],
    )


def _cap_reasons(assessment) -> list[str]:
    return [
        r
        for r in assessment.reasons
        if "per-trade max" in r or "aggregate planned SL risk" in r
    ]


def test_12_46_setup_is_no_longer_refused_by_the_reference_cap() -> None:
    # $4.88 at equity 63.65: 14% = $8.91 -> allowed.
    assessment = _evaluate("63.65", "4.88")
    assert _cap_reasons(assessment) == []
    assert assessment.decision is not RiskDecision.REJECT, assessment.reasons


def test_cap_follows_live_equity_down() -> None:
    # $8.00 at equity 50.00: 14% = $7.00 -> refused.
    assessment = _evaluate("50.00", "8.00")
    assert assessment.decision is RiskDecision.REJECT
    # $5.00 at equity 30.00: 14% = $4.20 -> refused.
    assessment = _evaluate("30.00", "5.00")
    assert assessment.decision is RiskDecision.REJECT
    # $4.00 at equity 30.00 fits 14% ($4.20).
    assert _evaluate("30.00", "4.00").decision is not RiskDecision.REJECT


def test_a_stricter_explicit_cap_still_binds() -> None:
    cfg = RiskEngineConfig(
        min_lot=D("0.01"),
        lot_step=D("0.01"),
        max_lot=D("0.01"),
        contract_size=D("100"),
        max_planned_sl_risk_usd=D("3.00"),
        max_total_planned_risk_usd=D("3.00"),
    )
    assessment = _evaluate("63.65", "4.88", cfg)
    assert assessment.decision is RiskDecision.REJECT


def test_owner_risk_cap_helper() -> None:
    ref = MAX_PLANNED_SL_RISK_USD
    assert ref == D("7.00")
    kw = {"configured": ref, "reference_default": ref}
    assert ol.owner_risk_cap_usd(equity=D("63.65"), **kw) == D("8.91")
    assert ol.owner_risk_cap_usd(equity=D("30"), **kw) == D("4.20")
    assert ol.owner_risk_cap_usd(equity=D("30"), positions=2, **kw) == D("8.40")
    # Unknown equity keeps the static value (other guards fail closed).
    assert ol.owner_risk_cap_usd(equity=None, **kw) == ref
    assert ol.owner_risk_cap_usd(
        equity=D("63.65"), configured=D("3.00"), reference_default=ref
    ) == D("3.00")
