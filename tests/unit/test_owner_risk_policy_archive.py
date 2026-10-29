"""Owner risk helper and the published hard caps it must not replace."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.execution.bridge import ExecutionBridge
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_PLANNED_RISK_PCT,
)
from app.domain.institutional_trading.owner_risk_policy import (
    MAX_DAILY_LOSS_PCT,
    MAX_PLANNED_RISK_PCT,
    daily_loss_exceeded,
    daily_loss_pct,
    planned_risk_cap_usd,
)
from services.mt5_gateway.order_guard import (
    OWNER_MAX_ENTRY_VOLUME,
    ClientOrderIdRegistry,
    OrderGuardRejected,
    enforce_order_guard,
)


@pytest.mark.unit
def test_owner_policy_module_uses_nine_and_nineteen() -> None:
    assert MAX_PLANNED_RISK_PCT == Decimal("9.0")
    assert MAX_DAILY_LOSS_PCT == Decimal("19.0")
    assert planned_risk_cap_usd(Decimal("1000")) == Decimal("90.00")
    assert planned_risk_cap_usd(Decimal("0")) == Decimal("0")


@pytest.mark.unit
def test_daily_loss_allows_the_exact_cap_and_rejects_the_next_step() -> None:
    exact = dict(
        equity=Decimal("810"),
        daily_pnl=Decimal("-190"),
        balance=Decimal("810"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    assert daily_loss_pct(
        equity=exact["equity"],
        daily_pnl=exact["daily_pnl"],
        balance=exact["balance"],
    ) == Decimal("19.00")
    assert daily_loss_exceeded(**exact) is False
    assert daily_loss_exceeded(
        equity=Decimal("809.90"),
        daily_pnl=Decimal("-190"),
        balance=Decimal("810"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    ) is True


@pytest.mark.unit
def test_published_hard_caps_stay_in_place() -> None:
    assert OWNER_MAX_PLANNED_RISK_PCT == Decimal("9.0")
    assert OWNER_DAILY_LOSS_PCT == Decimal("19.0")
    assert OWNER_MAX_LOT == Decimal("0.01")
    assert OWNER_MAX_ENTRY_VOLUME == 0.01
    cfg = AiScalpingConfig()
    assert cfg.risk_per_trade_pct == Decimal("0.50")
    assert cfg.max_daily_exposure_pct == Decimal("5.00")
    assert cfg.max_symbol_exposure_pct == Decimal("5.00")
    assert cfg.max_correlated_exposure_pct == Decimal("5.00")
    raised = AiScalpingConfig(risk_per_trade_pct=Decimal("9"))
    assert raised.risk_per_trade_pct == Decimal("0.75")


@pytest.mark.unit
def test_published_guard_still_rejects_volume_above_one_hundredth() -> None:
    with pytest.raises(OrderGuardRejected) as caught:
        enforce_order_guard(
            {
                "symbol": "XAUUSD",
                "action": "buy",
                "volume": 0.02,
                "sl": 9.0,
                "tp": 12.0,
                "client_order_id": "cap-check",
            },
            registry=ClientOrderIdRegistry(),
            equity=Decimal("1000"),
            quote=None,
            positions_lookup=lambda: [],
        )
    assert caught.value.code == "GUARD_MAX_LOT"


@pytest.mark.unit
def test_execution_bridge_still_checks_the_kill_switch_twice() -> None:
    source = inspect.getsource(ExecutionBridge.handle)
    assert source.count("self.kill_switch.enabled") == 2
    assert "OMS receives nothing" in source
