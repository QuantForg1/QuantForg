"""Regression: Risk/Eligibility must not apply gold max_spread to crypto/index."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.institutional_trading.ai_scalping.asset_class import (
    spread_reject_ceiling,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine


def _check(**kwargs: object) -> RiskCheckInput:
    base = {
        "user_id": uuid4(),
        "request_id": "spread-asset-class",
        "symbol": "BTCUSD",
        "side": "buy",
        "entry_price": Decimal("110000"),
        "stop_loss_distance": Decimal("500"),
        "spread": Decimal("22.25"),
        "session_allowed": True,
    }
    base.update(kwargs)
    return RiskCheckInput(**base)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.trading_core
def test_spread_reject_ceiling_is_asset_class_native() -> None:
    gold_policy = Decimal("1.50")
    assert spread_reject_ceiling("XAUUSD", policy_max_spread=gold_policy) == gold_policy
    assert spread_reject_ceiling("BTCUSD", policy_max_spread=gold_policy) == Decimal(
        "80"
    )
    assert spread_reject_ceiling("LTCUSD", policy_max_spread=gold_policy) == Decimal(
        "80"
    )
    assert spread_reject_ceiling("NDXUSD", policy_max_spread=gold_policy) == Decimal(
        "8.0"
    )
    assert spread_reject_ceiling("EURUSD", policy_max_spread=gold_policy) == Decimal(
        "0.00100"
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_risk_engine_does_not_reject_btc_on_gold_max_spread() -> None:
    """Live defect: BTCUSD spread ~22 rejected by gold max 1.50 after Safety PASS."""
    engine = RiskEngine(config=RiskEngineConfig(max_spread=Decimal("1.50")))
    ok, reasons = engine._institutional_gates(
        _check(symbol="BTCUSD", spread=Decimal("22.25"))
    )
    assert ok is True
    assert reasons == []


@pytest.mark.unit
@pytest.mark.trading_core
def test_risk_engine_accepts_ndx_under_index_ceiling() -> None:
    engine = RiskEngine(config=RiskEngineConfig(max_spread=Decimal("1.50")))
    ok, reasons = engine._institutional_gates(
        _check(
            symbol="NDXUSD",
            side="buy",
            entry_price=Decimal("20000"),
            stop_loss_distance=Decimal("50"),
            spread=Decimal("4.10"),
        )
    )
    assert ok is True
    assert reasons == []


@pytest.mark.unit
@pytest.mark.trading_core
def test_risk_engine_still_rejects_index_above_class_ceiling() -> None:
    engine = RiskEngine(config=RiskEngineConfig(max_spread=Decimal("1.50")))
    ok, reasons = engine._institutional_gates(
        _check(
            symbol="NDXUSD",
            entry_price=Decimal("20000"),
            stop_loss_distance=Decimal("50"),
            spread=Decimal("21.95"),
        )
    )
    assert ok is False
    assert any("8.0" in r for r in reasons)


@pytest.mark.unit
@pytest.mark.trading_core
def test_eligibility_accepts_ltc_spread_under_crypto_ceiling() -> None:
    cfg = ITEConfig(
        max_spread_reject=Decimal("1.50"),
        trading_mode="scalping",
    )

    class _Snap:
        symbol = "LTCUSD"
        spread = Decimal("0.35")
        session = type("S", (), {"allowed": True, "reason": "ok"})()
        news = type("N", (), {"blocked": False, "reason": ""})()
        trade_quality = type("Q", (), {"passed": True, "total": 80})()

    confluence = ConfluenceResult(
        passed=True,
        confidence=75,
        direction=TradeDirection.SELL,
        factors={},
        reasons=(),
        rejected_rules=(),
        input_hash="spread-test",
    )
    account = AccountRiskState(
        equity=Decimal("1000"),
        already_in_trade=False,
        open_positions=0,
        market_open=True,
        free_margin=Decimal("1000"),
    )
    result = PositionEligibilityEngine(config=cfg).evaluate(
        snapshot=_Snap(),  # type: ignore[arg-type]
        confluence=confluence,
        account=account,
        risk_allowed=True,
    )
    assert result.checks.get("spread_acceptable") is True
