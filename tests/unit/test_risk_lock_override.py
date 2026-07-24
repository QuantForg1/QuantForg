"""Unit tests for ALLOW_RISK_LOCK_OVERRIDE — daily loss only."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.risk_engine import RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.risk_lock_override import (
    apply_daily_loss_lock_override,
    is_daily_loss_lock_reason,
    risk_lock_override_enabled,
    risk_lock_override_status,
)


@pytest.fixture
def override_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.risk_lock_override.risk_lock_override_enabled",
        lambda settings=None: True,
    )


@pytest.fixture
def override_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.risk_lock_override.risk_lock_override_enabled",
        lambda settings=None: False,
    )


@pytest.mark.unit
def test_only_daily_loss_reasons_are_overridable() -> None:
    assert is_daily_loss_lock_reason("daily loss 6.64% exceeds 5%")
    assert is_daily_loss_lock_reason("Maximum daily loss exceeded")
    assert not is_daily_loss_lock_reason("weekly loss 12% exceeds 10%")
    assert not is_daily_loss_lock_reason("max drawdown 26% reaches 25%")
    assert not is_daily_loss_lock_reason("Insufficient free margin")
    assert not is_daily_loss_lock_reason("Market is closed")


@pytest.mark.unit
def test_apply_override_strips_daily_only(override_on: None) -> None:
    remaining, did = apply_daily_loss_lock_override(
        [
            "daily loss 6.64% exceeds 5%",
            "Insufficient free margin",
        ],
        log=False,
    )
    assert did is True
    assert remaining == ["Insufficient free margin"]


@pytest.mark.unit
def test_apply_override_noop_when_disabled(override_off: None) -> None:
    reasons = ["daily loss 6.64% exceeds 5%"]
    remaining, did = apply_daily_loss_lock_override(reasons, log=False)
    assert did is False
    assert remaining == reasons


@pytest.mark.unit
def test_evaluate_drawdown_override_keeps_other_locks(
    override_on: None,
) -> None:
    engine = RiskEngine(
        config=RiskEngineConfig(
            max_daily_loss_pct=Decimal("5"),
            max_weekly_loss_pct=Decimal("10"),
            max_drawdown_pct=Decimal("25"),
        )
    )
    account = AccountSnapshot(
        login=1,
        balance=Decimal("162.77"),
        equity=Decimal("162.77"),
        margin=Decimal("0"),
        free_margin=Decimal("162.77"),
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=1000,
    )
    # Daily loss alone → no reject reasons under override
    _, reasons, warnings = engine.evaluate_drawdown(
        account,
        daily_pnl=Decimal("-10.80"),
    )
    assert reasons == []
    assert any("daily loss lock overridden" in w for w in warnings)

    # Weekly still rejects
    _, reasons2, _ = engine.evaluate_drawdown(
        account,
        daily_pnl=Decimal("-10.80"),
        weekly_pnl=Decimal("-20"),
    )
    assert any("weekly loss" in r for r in reasons2)


@pytest.mark.unit
def test_evaluate_drawdown_rejects_without_override(override_off: None) -> None:
    engine = RiskEngine(config=RiskEngineConfig(max_daily_loss_pct=Decimal("5")))
    account = AccountSnapshot(
        login=1,
        balance=Decimal("162.77"),
        equity=Decimal("162.77"),
        margin=Decimal("0"),
        free_margin=Decimal("162.77"),
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=1000,
    )
    _, reasons, _ = engine.evaluate_drawdown(
        account,
        daily_pnl=Decimal("-10.80"),
    )
    assert any("daily loss" in r for r in reasons)


@pytest.mark.unit
def test_auto_trade_gate_passes_daily_loss_in_test_mode(
    override_on: None,
) -> None:
    facts = AutoTradeLiveFacts(
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        risk_engine_pass=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol="EURUSD",
        symbol_tradable=True,
        margin_available=True,
        no_broker_restrictions=True,
        open_positions=0,
        session="london",
        spread=Decimal("0.0005"),
        news_blocked=False,
        daily_loss_exceeded=True,
        emergency_stop=False,
        ops_mode="LIVE",
        execution_enabled=True,
    )
    result = evaluate_auto_trade_safety(
        AutoTradePolicy(enabled=True, run_state="running"),
        facts,
    )
    daily = next(c for c in result.conditions if c.key == "daily_loss")
    assert daily.passed is True
    assert "TEST MODE" in (daily.detail or "")


@pytest.mark.unit
def test_status_banner_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(allow_risk_lock_override=True)
    monkeypatch.setattr(
        "app.domain.institutional_trading.risk_lock_override.risk_lock_override_enabled",
        lambda s=None: bool(getattr(s or settings, "allow_risk_lock_override", False)),
    )
    status = risk_lock_override_status(settings)
    assert status["enabled"] is True
    assert status["banner"] is True
    assert status["message"] == "Daily loss lock overridden."
    assert risk_lock_override_enabled(settings) is True
