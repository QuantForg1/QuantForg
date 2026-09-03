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
        "spread": Decimal("0.00010"),
        "news_blocked": False,
        "daily_loss_exceeded": False,
        "emergency_stop": False,
        "ops_mode": "LIVE",
        "execution_enabled": True,
    }
    base.update(overrides)
    return AutoTradeLiveFacts(**base)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.trading_core
class TestAutoTradeSafetyGate:
    def test_enabled_when_all_conditions_pass(self) -> None:
        policy = AutoTradePolicy(enabled=True)
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is True
        assert result.status == "Enabled"
        assert result.failed_reasons == ()

    def test_paused_blocks_new_trades(self) -> None:
        policy = AutoTradePolicy(enabled=True, run_state="paused")
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is False
        assert any("PAUSED" in r for r in result.failed_reasons)

    def test_stopped_blocks_new_trades(self) -> None:
        policy = AutoTradePolicy(enabled=False, run_state="stopped")
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is False
        assert any("STOPPED" in r or "OFF" in r for r in result.failed_reasons)

    def test_running_allows_when_all_pass(self) -> None:
        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(policy, _all_pass_facts())
        assert result.allowed is True

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

    def test_scalping_allows_dynamic_universe_when_no_multi_symbol_list(self) -> None:
        """Dynamic path: single/default allowlist does not block discovered symbols."""
        policy = AutoTradePolicy(
            enabled=True,
            run_state="running",
            trading_mode="scalping",
            allowed_symbols=("XAUUSD",),
        )
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="AUDJPY", symbol_tradable=True),
        )
        assert result.allowed is True
        assert not any("not in allowed list" in r for r in result.failed_reasons)

    def test_scalping_enforces_operator_managed_multi_symbol_list(self) -> None:
        """Symbol Management multi-symbol allowlist gates post-strategy handoff."""
        policy = AutoTradePolicy(
            enabled=True,
            run_state="running",
            trading_mode="scalping",
            allowed_symbols=("XAUUSD", "EURUSD", "GBPUSD"),
        )
        blocked = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="AUDJPY", symbol_tradable=True),
        )
        assert blocked.allowed is False
        assert any("not in allowed list" in r for r in blocked.failed_reasons)
        ok = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="EURUSD", symbol_tradable=True),
        )
        assert ok.allowed is True

    def test_unverified_pnl_blocks_without_claiming_daily_loss(self) -> None:
        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(
                daily_pnl_verified=False,
                daily_loss_exceeded=False,
            ),
        )
        assert result.allowed is False
        assert any("unavailable" in r.lower() for r in result.failed_reasons)
        assert "Maximum daily loss exceeded" not in result.failed_reasons

    def test_legitimate_daily_loss_still_blocks(self) -> None:
        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(
                daily_pnl_verified=True,
                daily_loss_exceeded=True,
            ),
        )
        assert result.allowed is False
        assert any(
            "Maximum daily loss exceeded" in r for r in result.failed_reasons
        )

    def test_allowlist_xauusd_recognizes_broker_xauusd_i(self) -> None:
        """Desk-aware: configured XAUUSD authorizes catalogue XAUUSD_I."""
        policy = AutoTradePolicy(
            enabled=True,
            run_state="running",
            trading_mode="scalping",
            allowed_symbols=("XAUUSD", "EURUSD", "GBPUSD"),
        )
        ok = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="XAUUSD_I", symbol_tradable=True),
        )
        assert ok.allowed is True
        # LTCUSD still blocked — do not widen allowlist.
        blocked = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="LTCUSD", symbol_tradable=True),
        )
        assert blocked.allowed is False

    def test_swing_still_enforces_allowed_symbols(self) -> None:
        policy = AutoTradePolicy(
            enabled=True,
            run_state="running",
            trading_mode="swing",
            allowed_symbols=("XAUUSD", "EURUSD"),
        )
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="AUDJPY", symbol_tradable=True),
        )
        assert result.allowed is False
        assert any("not in allowed list" in r for r in result.failed_reasons)

    def test_gold_spread_above_two_usd_rejects_gold_only(self) -> None:
        from app.domain.institutional_trading.auto_trading import (
            safety_blocks_decision,
            safety_failure_scope,
        )
        from app.domain.trading.xauusd_specs import MAX_SPREAD

        assert Decimal("2.00") == MAX_SPREAD
        policy = AutoTradePolicy(enabled=True, run_state="running")
        blocked = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="XAUUSD", spread=Decimal("2.01")),
        )
        assert blocked.allowed is False
        assert safety_failure_scope(blocked) == "symbol"
        assert safety_blocks_decision(blocked) is False
        assert blocked.spread_diagnostics.get("spread_limit") == "2.00"
        assert blocked.spread_diagnostics.get("asset_class") == "gold"
        ok = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="XAUUSD", spread=Decimal("2.00")),
        )
        assert ok.allowed is True

    def test_fx_decimal_spread_is_not_gold_ceiling(self) -> None:
        from app.domain.institutional_trading.auto_trading import (
            safety_blocks_decision,
            safety_failure_scope,
        )

        policy = AutoTradePolicy(enabled=True, run_state="running")
        # 3.1 pips on a 5-digit major — would incorrectly PASS Gold's 2.00 USD.
        tight = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="EURUSD", spread=Decimal("0.00031")),
        )
        assert tight.allowed is True
        wide = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="EURUSD", spread=Decimal("0.00200")),
        )
        assert wide.allowed is False
        assert safety_failure_scope(wide) == "symbol"
        assert safety_blocks_decision(wide) is False
        assert "gold" not in str(wide.spread_diagnostics.get("asset_class"))
        limit = Decimal(str(wide.spread_diagnostics.get("spread_limit")))
        assert limit < Decimal("2.00")

    def test_global_autotrading_false_still_blocks_universe(self) -> None:
        from app.domain.institutional_trading.auto_trading import (
            safety_blocks_decision,
            safety_failure_scope,
        )

        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(mt5_autotrading_enabled=False),
        )
        assert result.allowed is False
        assert safety_failure_scope(result) == "global"
        assert safety_blocks_decision(result) is True
        assert any("AutoTrading is disabled" in r for r in result.failed_reasons)

    def test_mixed_global_and_spread_stays_global(self) -> None:
        from app.domain.institutional_trading.auto_trading import (
            safety_blocks_decision,
            safety_failure_scope,
        )

        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(
                mt5_autotrading_enabled=False,
                symbol="XAUUSD",
                spread=Decimal("9.04"),
            ),
        )
        assert safety_failure_scope(result) == "global"
        assert safety_blocks_decision(result) is True

    def test_unknown_instrument_spread_fails_that_symbol_only(self) -> None:
        from app.domain.institutional_trading.auto_trading import (
            safety_blocks_decision,
            safety_failure_scope,
        )

        policy = AutoTradePolicy(enabled=True, run_state="running")
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(symbol="FOO", spread=Decimal("0.10")),
        )
        assert result.allowed is False
        assert safety_failure_scope(result) == "symbol"
        assert safety_blocks_decision(result) is False


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

        from app.domain.institutional_trading.live_trading_control import (
            reset_live_trading_controller_for_tests,
        )

        ctrl = reset_live_trading_controller_for_tests()
        ctrl.transition(op, "ARMED", confirmed=True, reason="test-arm")
        ctrl.transition(op, "ENABLED", confirmed=True, reason="test-enable")

        safety = plane.evaluate_auto_trading(_all_pass_facts(ops_mode="LIVE"))
        assert safety.allowed is True

        plane.emergency_stop(op, reason="halt", confirmed=True)
        assert plane.auto_trading_enabled is False
        assert plane.kill_switch_armed is True
        blocked = plane.evaluate_auto_trading(_all_pass_facts(ops_mode="LIVE"))
        assert blocked.allowed is False
        assert blocked.status == "Disabled"
