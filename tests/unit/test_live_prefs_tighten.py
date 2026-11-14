"""Customer Risk Center prefs tighten LIVE RiskEngineConfig only."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.institutional_trading.operations.live_prefs_tighten import (
    tighten_live_risk_config_for_user,
    tighten_risk_config_from_effective,
)


def test_effective_prefs_only_tighten_ceilings() -> None:
    base = RiskEngineConfig(
        max_lot=Decimal("0.01"),
        max_risk_per_trade_pct=Decimal("20"),
        max_daily_loss_pct=Decimal("48"),
        max_open_positions=3,
        fixed_lot=Decimal("0.01"),
    )
    out = tighten_risk_config_from_effective(
        base,
        {
            "ok": True,
            "planned_risk_pct": "10",
            "max_lot": "0.01",
            "daily_loss_pct": "20",
            "max_concurrent_positions": 1,
        },
    )
    assert out.max_risk_per_trade_pct == Decimal("10")
    assert out.max_daily_loss_pct == Decimal("20")
    assert out.max_open_positions == 1
    assert out.max_lot == Decimal("0.01")


def test_effective_prefs_cannot_loosen_owner_ceilings() -> None:
    base = RiskEngineConfig(
        max_lot=Decimal("0.01"),
        max_risk_per_trade_pct=Decimal("5"),
        max_daily_loss_pct=Decimal("10"),
        max_open_positions=1,
        fixed_lot=Decimal("0.01"),
    )
    out = tighten_risk_config_from_effective(
        base,
        {
            "ok": True,
            "planned_risk_pct": "20",
            "max_lot": "1.00",
            "daily_loss_pct": "48",
            "max_concurrent_positions": 5,
        },
    )
    assert out.max_risk_per_trade_pct == Decimal("5")
    assert out.max_lot == Decimal("0.01")
    assert out.max_daily_loss_pct == Decimal("10")
    assert out.max_open_positions == 1


def test_missing_user_leaves_config_unchanged() -> None:
    base = RiskEngineConfig()
    assert tighten_live_risk_config_for_user(base, None) is base


def test_prefs_load_failure_leaves_owner_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = RiskEngineConfig(max_risk_per_trade_pct=Decimal("15"))

    def _raise(_uid: object) -> dict:
        raise RuntimeError("prefs unavailable")

    monkeypatch.setattr(
        "app.application.services.user_risk_preferences_service.get_user_risk_preferences",
        _raise,
    )
    out = tighten_live_risk_config_for_user(base, uuid4())
    assert out.max_risk_per_trade_pct == Decimal("15")
