"""Execution worker continuity diagnostics — never enables trading."""

from __future__ import annotations

import pytest

from app.application.services.execution_worker_status import (
    collect_execution_worker_status,
)
from app.application.services.openai_advisor_service import (
    _record_openai_error,
    clear_openai_provider_error_for_tests,
    last_openai_provider_error,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.live_trading_control import (
    get_live_trading_controller,
    orders_may_submit,
    reset_live_trading_controller_for_tests,
)
from core.config.environments import testing_settings


@pytest.fixture(autouse=True)
def _reset_live() -> None:
    reset_live_trading_controller_for_tests()
    clear_openai_provider_error_for_tests()
    yield
    reset_live_trading_controller_for_tests()
    clear_openai_provider_error_for_tests()


@pytest.mark.unit
def test_disabled_live_trading_blocks_orders_may_submit() -> None:
    ctrl = get_live_trading_controller()
    assert ctrl.snapshot_state() == "DISABLED"
    assert orders_may_submit(ctrl.snapshot_state()) is False


@pytest.mark.unit
def test_auto_trade_safety_blocks_when_live_trading_disabled() -> None:
    policy = AutoTradePolicy(
        enabled=True,
        run_state="running",
        max_open_positions=1,
        risk_per_trade_pct=0.5,
        max_daily_loss_pct=3.0,
        allowed_sessions=("all",),
        allowed_symbols=("XAUUSD",),
        max_spread=2.0,
        news_filter_enabled=False,
        trading_mode="scalping",
        compounding_enabled=False,
        alpha_engine_enabled=False,
    )
    facts = AutoTradeLiveFacts(
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        risk_engine_pass=True,
        risk_engine_reasons=(),
        risk_engine_evaluated=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        mt5_autotrading_known=True,
        account_flags_evaluated=True,
        symbol="XAUUSD",
        symbol_tradable=True,
        margin_available=True,
        margin_evaluated=True,
        no_broker_restrictions=True,
        open_positions=0,
        session="london",
        session_evaluated=True,
        broker_session_open=True,
        session_source="test",
        spread=0.5,
        spread_evaluated=True,
        news_blocked=False,
        news_reason="",
        daily_loss_exceeded=False,
        daily_pnl_verified=True,
        deposit_verification=True,
        emergency_stop=False,
        ops_mode="LIVE",
        execution_enabled=True,
        live_trading_state="DISABLED",
    )
    result = evaluate_auto_trade_safety(policy, facts)
    assert result.allowed is False
    assert any("LIVE TRADING is DISABLED" in r for r in result.failed_reasons)


@pytest.mark.unit
def test_execution_worker_status_reports_disabled_blocker() -> None:
    settings = testing_settings(execution_enabled=True)
    payload = collect_execution_worker_status(settings)
    assert payload["execution_enabled"] is True
    assert payload["live_trading"]["orders_may_submit"] is False
    assert payload["continuous_trading_authorized"] is False
    assert any("DISABLED" in b for b in payload["blockers"])


@pytest.mark.unit
def test_openai_quota_error_recorded_as_advisory_degraded() -> None:
    _record_openai_error(
        "insufficient_quota", "OpenAI account has no remaining API credits"
    )
    err = last_openai_provider_error()
    assert err is not None
    assert err["code"] == "insufficient_quota"
    settings = testing_settings(execution_enabled=True)
    payload = collect_execution_worker_status(settings)
    assert payload["openai"]["degraded"] is True
    # Quota does not hard-block OMS path.
    assert not any(str(b).startswith("openai_degraded") for b in payload["blockers"])
    assert any("openai_degraded" in str(b) for b in payload["advisory_blockers"])
