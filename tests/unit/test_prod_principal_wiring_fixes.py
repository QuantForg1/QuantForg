"""Regression: production principal wiring fixes (no strategy/risk changes)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    _cycle_flag_prefer_context,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from core.config.settings import AppEnvironment, Settings


def test_cycle_flag_prefers_context_over_stale_enrich_false() -> None:
    assert (
        _cycle_flag_prefer_context(
            ctx_value=True,
            enrich={"mt5_autotrading_enabled": False},
            key="mt5_autotrading_enabled",
        )
        is True
    )


def test_cycle_flag_uses_enrich_when_context_matches() -> None:
    assert (
        _cycle_flag_prefer_context(
            ctx_value=False,
            enrich={"mt5_autotrading_enabled": False},
            key="mt5_autotrading_enabled",
        )
        is False
    )


def test_cycle_flag_falls_back_to_context_when_enrich_missing() -> None:
    assert (
        _cycle_flag_prefer_context(
            ctx_value=True,
            enrich={},
            key="mt5_autotrading_enabled",
        )
        is True
    )


def test_run_auto_cycle_keeps_kwargs_connectivity_when_probes_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flaky live_probes=False must not SAFETY_BLOCK after proven context."""
    captured: dict[str, Any] = {}

    plane = MagicMock()
    plane.mode = OpsExecutionMode.LIVE
    plane.kill_switch_armed = False
    plane.daily_loss_exceeded = False

    def _eval(facts: Any) -> SimpleNamespace:
        captured["gateway"] = facts.gateway_connected
        captured["broker"] = facts.broker_connected
        return SimpleNamespace(allowed=False, failed_reasons=("test block",))

    plane.evaluate_auto_trading = _eval

    runtime = InstitutionalIteRuntime(
        plane=plane,
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
        interval_seconds=5.0,
        mt5_adapter=MagicMock(execution_enabled=True),
    )
    runtime.tick_health = MagicMock(  # type: ignore[method-assign]
        return_value={
            "health": "ok",
            "live_probes": {"gateway": False, "mt5": False},
        }
    )
    runtime._sync_and_manage_open_positions = lambda **_k: 0  # type: ignore[method-assign]
    runtime._run_cycle = MagicMock()  # type: ignore[method-assign]

    monkeypatch.setattr(
        "app.application.services.institutional_ite_runtime.get_settings",
        lambda: SimpleNamespace(execution_enabled=True),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.force_first_trade.is_force_first_trade_armed",
        lambda _settings=None: False,
    )

    account = AccountRiskState(
        equity=__import__("decimal").Decimal("1000"),
        free_margin=__import__("decimal").Decimal("900"),
        open_positions=0,
        already_in_trade=False,
        daily_pnl=__import__("decimal").Decimal("0"),
        peak_equity=__import__("decimal").Decimal("1000"),
    )
    snapshot = MagicMock()

    result = runtime.run_auto_cycle(
        snapshot=snapshot,
        account=account,
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        risk_allowed=True,
    )

    assert captured["gateway"] is True
    assert captured["broker"] is True
    assert result.abort_reason == "SAFETY_BLOCKED"
    runtime._run_cycle.assert_not_called()


def test_production_execution_enabled_requires_caller_token() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        railway_public_domain="quantforg-production.up.railway.app",
        allowed_hosts=["quantforg-production.up.railway.app"],  # type: ignore[arg-type]
        execution_enabled=True,
        mt5_gateway_base_url="https://gateway.example.com",
        mt5_gateway_caller_token="",
    )
    assert settings.execution_enabled is False


def test_production_execution_enabled_stays_true_with_url_and_token() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        railway_public_domain="quantforg-production.up.railway.app",
        allowed_hosts=["quantforg-production.up.railway.app"],  # type: ignore[arg-type]
        execution_enabled=True,
        mt5_gateway_base_url="https://gateway.example.com",
        mt5_gateway_caller_token="shared-secret-token-value",
    )
    assert settings.execution_enabled is True
