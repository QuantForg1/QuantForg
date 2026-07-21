"""Unit tests — Auto Trading safety gate + ops controls."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.live_auto_trade_certification import (
    seed_certified_demo_report_for_tests,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Auto Trade Tester",
    )


def _all_pass_facts(**overrides: object) -> AutoTradeLiveFacts:
    base: dict[str, object] = {
        "gateway_connected": True,
        "broker_connected": True,
        "market_data_live": True,
        "risk_engine_pass": True,
        "account_trading_enabled": True,
        "mt5_autotrading_enabled": True,
        "symbol": "XAUUSD",
        "symbol_tradable": True,
        "margin_available": True,
        "no_broker_restrictions": True,
        "open_positions": 0,
        "session": "london",
        "spread": Decimal("0.40"),
        "news_blocked": False,
        "daily_loss_exceeded": False,
        "emergency_stop": False,
        "ops_mode": "LIVE",
        "execution_enabled": True,
    }
    base.update(overrides)
    return AutoTradeLiveFacts(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestAutoTradeSafetyGate:
    def test_enabled_when_all_conditions_pass(self) -> None:
        policy = AutoTradePolicy(enabled=True)
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is True
        assert result.status == "Enabled"
        assert result.failed_reasons == ()

    def test_disabled_when_toggle_off(self) -> None:
        policy = AutoTradePolicy(enabled=False)
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is False
        assert result.status == "Disabled"
        assert any("toggle" in r.lower() or "OFF" in r for r in result.failed_reasons)

    def test_risk_engine_failure_blocks(self) -> None:
        policy = AutoTradePolicy(enabled=True)
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(
                risk_engine_pass=False,
                risk_engine_reasons=("Daily loss limit",),
            ),
        )
        assert result.allowed is False
        assert "Daily loss limit" in result.failed_reasons

    def test_news_filter_blocks_when_enabled(self) -> None:
        policy = AutoTradePolicy(enabled=True, news_filter_enabled=True)
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(news_blocked=True, news_reason="NFP blackout"),
        )
        assert result.allowed is False
        assert "NFP blackout" in result.failed_reasons

    def test_spread_limit(self) -> None:
        policy = AutoTradePolicy(enabled=True, max_spread=Decimal("1.00"))
        result = evaluate_auto_trade_safety(
            policy, _all_pass_facts(spread=Decimal("1.50"))
        )
        assert result.allowed is False
        assert any("Spread" in r for r in result.failed_reasons)

    def test_missing_spread_fail_closed(self) -> None:
        policy = AutoTradePolicy(enabled=True, max_spread=Decimal("1.00"))
        result = evaluate_auto_trade_safety(policy, _all_pass_facts(spread=None))
        assert result.allowed is False
        assert any("Spread" in r for r in result.failed_reasons)


@pytest.mark.unit
class TestAutoTradeOpsControls:
    def test_update_controls_and_emergency_stop(self) -> None:
        seed_certified_demo_report_for_tests()
        plane = OperationsControlPlane()
        op = _op()
        plane.transition_mode(
            op, OpsExecutionMode.CANARY, reason="canary", confirmed=True
        )
        plane.transition_mode(op, OpsExecutionMode.LIVE, reason="live", confirmed=True)

        policy = plane.update_auto_trade_controls(
            op,
            enabled=True,
            max_open_positions=2,
            risk_per_trade_pct=Decimal("0.75"),
            max_daily_loss_pct=Decimal("2.5"),
            allowed_sessions=("london", "new_york"),
            allowed_symbols=("XAUUSD",),
            max_spread=Decimal("1.25"),
            news_filter_enabled=True,
            reason="configure auto trade",
        )
        assert policy.enabled is True
        assert policy.max_open_positions == 2
        assert policy.news_filter_enabled is True

        safety = plane.evaluate_auto_trading(_all_pass_facts(ops_mode="LIVE"))
        assert safety.allowed is True

        plane.emergency_stop(op, reason="halt", confirmed=True)
        assert plane.auto_trading_enabled is False
        assert plane.kill_switch_armed is True
        blocked = plane.evaluate_auto_trading(_all_pass_facts(ops_mode="LIVE"))
        assert blocked.allowed is False
        assert blocked.status == "Disabled"
