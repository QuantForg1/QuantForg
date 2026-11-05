"""P0: owner-authorized volume ceiling — never submit above max_lot 0.01.

Reproduces the LIVE HQ momentum near-miss path where target-risk sizing
preferred 0.02 lot against broker volume_max, then failed OWNER_SL_RISK.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_decision_pipeline import (
    risk_config_from_ite,
)
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    normalize_lots_against_broker,
)
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MAX_LOT,
    evaluate_owner_entry,
    max_planned_risk_usd,
    owner_authorized_max_lot,
    planned_risk_usd,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

D = Decimal
_GOLD_CS = D("100")
_STEP = D("0.01")
_MIN = D("0.01")
# LIVE near-miss geometry (NOC OWNER_SL_RISK dump).
_LIVE_EQUITY = D("15.52")
_LIVE_STOP = D("1.2671428600")
_LIVE_SPREAD = D("0.424")


def _account(equity: Decimal) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=D("0"),
        free_margin=equity,
        margin_level=D("0"),
        profit=D("0"),
        leverage=1000,
    )


def test_owner_authorized_max_lot_never_exceeds_ceiling() -> None:
    assert owner_authorized_max_lot(None) == OWNER_MAX_LOT
    assert owner_authorized_max_lot(D("100")) == OWNER_MAX_LOT
    assert owner_authorized_max_lot(D("0.01")) == OWNER_MAX_LOT
    assert owner_authorized_max_lot(D("0.005")) == D("0.005")


def test_risk_config_from_ite_clamps_broker_max_to_owner_ceiling() -> None:
    cfg = risk_config_from_ite(
        DEFAULT_ITE_CONFIG,
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=D("100"),
        contract_size=_GOLD_CS,
    )
    assert cfg.max_lot == OWNER_MAX_LOT
    assert cfg.max_lot <= OWNER_MAX_LOT


def test_normalize_with_owner_capped_max_never_returns_002() -> None:
    # Callers must pass owner_authorized_max_lot(broker_max). With that ceiling,
    # target-risk raw ~0.024 cannot become 0.02.
    out = normalize_lots_against_broker(
        calculated_lot=D("0.024"),
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=owner_authorized_max_lot(D("100")),
        equity=_LIVE_EQUITY,
        stop_distance=_LIVE_STOP,
        contract_size=_GOLD_CS,
        risk_budget=max_planned_risk_usd(_LIVE_EQUITY),
        min_planned_risk=D("0"),
        max_planned_sl_risk=max_planned_risk_usd(_LIVE_EQUITY),
    )
    assert out.approved is True
    assert out.normalized_lot == OWNER_MAX_LOT
    assert out.normalized_lot != D("0.02")


def test_planned_002_candidate_normalized_to_001_when_001_passes_owner_sl_risk() -> (
    None
):
    risk_at_002 = planned_risk_usd(
        stop_distance=_LIVE_STOP,
        spread=_LIVE_SPREAD,
        contract_size=_GOLD_CS,
        volume=D("0.02"),
        commission=D("0"),
    )
    risk_at_001 = planned_risk_usd(
        stop_distance=_LIVE_STOP,
        spread=_LIVE_SPREAD,
        contract_size=_GOLD_CS,
        volume=OWNER_MAX_LOT,
        commission=D("0"),
    )
    cap = max_planned_risk_usd(_LIVE_EQUITY)
    assert risk_at_002 > cap
    assert risk_at_001 <= cap

    engine = RiskEngine(
        config=RiskEngineConfig(
            min_lot=_MIN,
            lot_step=_STEP,
            max_lot=D("100"),  # buggy LIVE wiring — must still clamp
            contract_size=_GOLD_CS,
            min_planned_risk_usd=D("0"),
            target_risk_per_trade_usd=max_planned_risk_usd(_LIVE_EQUITY),
            max_planned_sl_risk_usd=max_planned_risk_usd(_LIVE_EQUITY),
        )
    )
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="p0-live-near-miss",
            symbol="XAUUSD",
            side="buy",
            requested_lots=None,
            stop_loss_distance=_LIVE_STOP,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=D("4000"),
            contract_size=_GOLD_CS,
            spread=_LIVE_SPREAD,
            slippage=D("0"),
            commission=D("0"),
            session_allowed=True,
        ),
        account=_account(_LIVE_EQUITY),
        positions=[],
    )
    assert result.approved_lots <= OWNER_MAX_LOT
    assert result.approved_lots != D("0.02")
    assert result.approved_lots == OWNER_MAX_LOT
    assert not any("OWNER_SL_RISK" in r for r in result.reasons)
    assert result.decision in {RiskDecision.ALLOW, RiskDecision.REDUCE_SIZE}
    assert result.approved_lots > 0


def test_owner_sl_risk_still_rejects_when_even_min_lot_exceeds_cap() -> None:
    # Stop-only risk fits normalize band ($2.80 <= $3.10) but inclusive
    # stop+spread at 0.01 exceeds the 20% owner cap → OWNER_SL_RISK.
    stop = D("2.80")
    cap = max_planned_risk_usd(_LIVE_EQUITY)
    stop_only = (stop * _GOLD_CS * OWNER_MAX_LOT).quantize(D("0.01"))
    inclusive = planned_risk_usd(
        stop_distance=stop,
        spread=_LIVE_SPREAD,
        contract_size=_GOLD_CS,
        volume=OWNER_MAX_LOT,
        commission=D("0"),
    )
    assert stop_only <= cap
    assert inclusive > cap

    engine = RiskEngine(
        config=risk_config_from_ite(
            DEFAULT_ITE_CONFIG,
            min_lot=_MIN,
            lot_step=_STEP,
            max_lot=D("100"),
            contract_size=_GOLD_CS,
        )
    )
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="p0-wide-sl",
            symbol="XAUUSD",
            side="buy",
            requested_lots=OWNER_MAX_LOT,
            stop_loss_distance=stop,
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=D("4000"),
            contract_size=_GOLD_CS,
            spread=_LIVE_SPREAD,
            commission=D("0"),
            session_allowed=True,
        ),
        account=_account(_LIVE_EQUITY),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == D("0")
    assert any("OWNER_SL_RISK" in r for r in result.reasons)


def test_broker_min_above_owner_max_is_rejected() -> None:
    engine = RiskEngine(
        config=RiskEngineConfig(
            min_lot=D("0.02"),
            lot_step=_STEP,
            max_lot=OWNER_MAX_LOT,
            contract_size=_GOLD_CS,
        )
    )
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="p0-broker-min",
            symbol="XAUUSD",
            side="buy",
            stop_loss_distance=_LIVE_STOP,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=D("4000"),
            contract_size=_GOLD_CS,
            spread=_LIVE_SPREAD,
            commission=D("0"),
            session_allowed=True,
        ),
        account=_account(_LIVE_EQUITY),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == D("0")
    assert any("OWNER_BROKER_MIN_EXCEEDS_MAX_LOT" in r for r in result.reasons)


def test_broker_volume_step_respected_when_clamping() -> None:
    out = normalize_lots_against_broker(
        calculated_lot=D("0.029"),
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=owner_authorized_max_lot(D("50")),
        equity=D("50"),
        stop_distance=D("1.00"),
        contract_size=_GOLD_CS,
        risk_budget=D("10"),
        min_planned_risk=D("0"),
    )
    assert out.approved is True
    assert out.normalized_lot == OWNER_MAX_LOT
    steps = out.normalized_lot / _STEP
    assert steps == steps.to_integral_value()


def test_evaluate_owner_entry_rejects_missing_sl_and_volume_002() -> None:
    base = {
        "symbol": "XAUUSD",
        "side": "buy",
        "volume": OWNER_MAX_LOT,
        "entry": D("4000"),
        "stop_loss": D("3998.73"),
        "take_profit": D("4001.50"),
        "spread": _LIVE_SPREAD,
        "contract_size": _GOLD_CS,
        "equity": _LIVE_EQUITY,
        "commission": D("0"),
    }
    assert any(
        r.startswith("OWNER_SL_REQUIRED")
        for r in evaluate_owner_entry(**{**base, "stop_loss": None})  # type: ignore[arg-type]
    )
    assert any(
        r.startswith("OWNER_MAX_LOT")
        for r in evaluate_owner_entry(**{**base, "volume": D("0.02")})  # type: ignore[arg-type]
    )


def test_all_registered_strategies_share_owner_lot_ceiling() -> None:
    # Ceiling is policy-global, not strategy-local. Every registry strategy
    # inherits the same authoritative owner max lot at Risk/normalize.
    ids = {s.strategy_id for s in ALL_STRATEGIES}
    assert len(ids) == 5
    assert "momentum_scalping" in ids
    assert "breakout_scalping" in ids
    assert "range_mean_reversion" in ids
    for _sid in ids:
        assert owner_authorized_max_lot(D("100")) == OWNER_MAX_LOT


def test_forced_requested_lots_002_never_approved_above_owner_max() -> None:
    engine = RiskEngine(
        config=risk_config_from_ite(
            DEFAULT_ITE_CONFIG,
            min_lot=_MIN,
            lot_step=_STEP,
            max_lot=D("100"),
            contract_size=_GOLD_CS,
        )
    )
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="p0-forced-002",
            symbol="XAUUSD",
            side="buy",
            requested_lots=D("0.02"),
            stop_loss_distance=_LIVE_STOP,
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=D("4000"),
            contract_size=_GOLD_CS,
            spread=_LIVE_SPREAD,
            commission=D("0"),
            session_allowed=True,
        ),
        account=_account(_LIVE_EQUITY),
        positions=[],
    )
    assert result.approved_lots <= OWNER_MAX_LOT
    assert result.approved_lots != D("0.02")
    if result.approved_lots > 0:
        assert result.approved_lots == OWNER_MAX_LOT
        assert not any("OWNER_SL_RISK" in r for r in result.reasons)
