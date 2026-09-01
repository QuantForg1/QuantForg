"""Phase 73 — controlled live trading authorization and safety gates.

Does not send orders. Does not auto-enable after restart.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.live_trading_control import (
    ACCOUNT_TOO_SMALL,
    HARD_CEILING_DAILY_LOSS_PCT,
    HARD_CEILING_RISK_PER_TRADE_PCT,
    BrokerSymbolSpec,
    LiveOrderRequest,
    LiveTradingAuthError,
    LiveTradingRiskConfig,
    LiveTradingTransitionError,
    evaluate_live_order,
    recover_after_restart,
    reset_live_trading_controller_for_tests,
    size_from_broker_specs,
    spec_from_broker,
    strip_secrets,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    RESEARCH_MAY_EXECUTE,
)
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.presentation.dependencies.auth import require_roles


def _op(role: str = "owner") -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role=role,
        display_name="Phase73 Tester",
    )


def _user(role: str) -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email=f"{role}@example.com",
        display_name=role,
        role=role,
        status="active",
        auth_user_id=uuid4(),
    )


def _spec(**overrides: object) -> BrokerSymbolSpec:
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "contract_size": Decimal("100000"),
        "volume_min": Decimal("0.01"),
        "volume_max": Decimal("100"),
        "volume_step": Decimal("0.01"),
        "tick_value": Decimal("1"),
        "tick_size": Decimal("0.00001"),
        "leverage": Decimal("500"),
        "stops_level": Decimal("10"),
        "freeze_level": Decimal("0"),
        "spread": Decimal("0.00012"),
        "trade_mode": "full",
        "trade_allowed": True,
        "market_open": True,
    }
    base.update(overrides)
    return BrokerSymbolSpec(**base)  # type: ignore[arg-type]


def _req(**overrides: object) -> LiveOrderRequest:
    spec = overrides.pop("spec", _spec()) if "spec" in overrides else _spec()
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "price": Decimal("1.10000"),
        "entry": Decimal("1.10000"),
        "stop_loss": Decimal("1.09900"),
        "take_profit": Decimal("1.10200"),
        "score": Decimal("80"),
        "edge": Decimal("9"),
        "regime": "TREND",
        "spread": Decimal("0.00012"),
        "quote_age_seconds": Decimal("1"),
        "analysis_age_seconds": Decimal("20"),
        "signal_id": "sig-1",
        "signal_status": "QUALIFIED",
        "evidence": {"WHY_THIS_DIRECTION": "structure + momentum"},
        "reward_risk": Decimal("2.0"),
        "spec": spec,
        "equity": Decimal("33"),
        "balance": Decimal("33"),
        "free_margin": Decimal("33"),
        "used_margin": Decimal("0"),
        "open_positions": 0,
        "open_exposure_pct": Decimal("0"),
        "correlated_exposure_pct": Decimal("0"),
        "daily_loss_pct": Decimal("0"),
        "consecutive_losses": 0,
        "slippage": Decimal("0.1"),
        "gateway_online": True,
        "mt5_connected": True,
        "ownership_ok": True,
        "account_available": True,
        "trading_permitted": True,
        "symbol_available": True,
        "symbol_tradeable": True,
        "quote_fresh": True,
        "price_valid": True,
        "market_open": True,
        "oms_healthy": True,
        "risk_engine_healthy": True,
        "audit_healthy": True,
        "authenticated_authorized": True,
        "request_id": "req-1",
    }
    base.update(overrides)
    return LiveOrderRequest(**base)  # type: ignore[arg-type]


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
        "live_trading_state": "ENABLED",
    }
    base.update(overrides)
    return AutoTradeLiveFacts(**base)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset_live() -> None:
    reset_live_trading_controller_for_tests()


@pytest.mark.unit
@pytest.mark.trading_core
def test_default_disabled_and_research_cannot_execute() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    assert ctrl.snapshot_state() == "DISABLED"
    assert ctrl.research_can_execute() is False
    assert RESEARCH_MAY_EXECUTE is False
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD")


@pytest.mark.unit
@pytest.mark.trading_core
def test_unauthorized_enable() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    with pytest.raises(LiveTradingAuthError):
        ctrl.transition(_op("trader"), "ARMED", confirmed=True, reason="no")


@pytest.mark.unit
@pytest.mark.trading_core
def test_authorized_arm_enable_double_confirmation() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    with pytest.raises(LiveTradingTransitionError):
        ctrl.transition(op, "ARMED", confirmed=False, reason="arm")
    with pytest.raises(LiveTradingTransitionError):
        ctrl.transition(op, "ENABLED", confirmed=True, reason="skip_arm")
    assert ctrl.transition(op, "ARMED", confirmed=True, reason="arm") == "ARMED"
    assert ctrl.research_can_execute() is False
    with pytest.raises(LiveTradingTransitionError):
        ctrl.transition(op, "ENABLED", confirmed=False, reason="enable")
    assert ctrl.transition(op, "ENABLED", confirmed=True, reason="enable") == "ENABLED"
    assert ctrl.research_can_execute() is True
    assert any(e.action == "transition_disabled_armed" for e in ctrl.audit)
    assert any(e.action == "transition_armed_enabled" for e in ctrl.audit)


@pytest.mark.unit
@pytest.mark.trading_core
def test_pause_kill_reset() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op("admin")
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    assert ctrl.transition(op, "PAUSED", confirmed=True, reason="pause") == "PAUSED"
    assert ctrl.research_can_execute() is False
    assert ctrl.transition(op, "ENABLED", confirmed=True, reason="resume") == "ENABLED"
    assert ctrl.transition(op, "KILLED", confirmed=True, reason="kill") == "KILLED"
    with pytest.raises(LiveTradingTransitionError):
        ctrl.transition(op, "ENABLED", confirmed=True, reason="no")
    assert ctrl.transition(op, "DISABLED", confirmed=True, reason="reset") == "DISABLED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_restart_recovery_never_auto_enables() -> None:
    assert recover_after_restart("ENABLED") == "PAUSED"
    assert recover_after_restart("LIVE_ENABLED") == "PAUSED"
    assert recover_after_restart("ARMED") == "DISABLED"
    assert recover_after_restart("READY_FOR_REVIEW") == "DISABLED"
    assert recover_after_restart("PAUSED") == "PAUSED"
    assert recover_after_restart("KILLED") == "DISABLED"
    assert recover_after_restart(None) == "DISABLED"
    ctrl = reset_live_trading_controller_for_tests()
    recovered = ctrl.hydrate({"live_trading_state": "ENABLED"})
    assert recovered == "PAUSED"
    assert ctrl.research_can_execute() is False
    assert ctrl.recovered_from_enabled is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_restart_hydrate_does_not_persist_paused_over_enabled() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        hydrate_live_trading_from_ops_state,
    )

    reset_live_trading_controller_for_tests()
    with patch(
        "app.application.services.live_trading_control_service.persist_live_trading"
    ) as persist:
        recovered = hydrate_live_trading_from_ops_state(
            {"live_trading_state": "ENABLED"}
        )
    assert recovered == "PAUSED"
    persist.assert_not_called()


@pytest.mark.unit
@pytest.mark.trading_core
def test_restart_hydrate_persists_when_dropping_incomplete_arm() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        hydrate_live_trading_from_ops_state,
    )

    reset_live_trading_controller_for_tests()
    with patch(
        "app.application.services.live_trading_control_service.persist_live_trading"
    ) as persist:
        recovered = hydrate_live_trading_from_ops_state({"live_trading_state": "ARMED"})
    assert recovered == "DISABLED"
    persist.assert_called_once()


_PASS_PROBE_FACTS = {
    "gateway_online": True,
    "mt5_connected": True,
    "mt5_attached": True,
    "ownership": "OWNED",
    "account_available": True,
    "equity": Decimal("33.12"),
    "balance": Decimal("33.12"),
}


@pytest.mark.unit
@pytest.mark.trading_core
def test_safe_recovery_resumes_only_when_probes_pass() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        resume_live_trading_after_safe_recovery,
    )

    ctrl = reset_live_trading_controller_for_tests()
    recovered = ctrl.hydrate({"live_trading_state": "ENABLED"})
    assert recovered == "PAUSED"
    assert ctrl.research_can_execute() is False
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value={
            "gateway_online": False,
            "mt5_connected": False,
            "mt5_attached": False,
            "ownership": "NOT_OWNED",
            "account_available": False,
        },
    ), patch(
        "app.application.services.live_trading_control_service.persist_live_trading",
        return_value=True,
    ):
        assert resume_live_trading_after_safe_recovery() == "PAUSED"
        assert ctrl.research_can_execute() is False
        assert ctrl.recovered_from_enabled is True
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value=_PASS_PROBE_FACTS,
    ), patch(
        "app.application.services.live_trading_control_service.persist_live_trading",
        return_value=True,
    ), patch(
        "app.domain.institutional_trading.operations.control_plane.get_control_plane",
    ):
        assert resume_live_trading_after_safe_recovery() == "ENABLED"
    assert ctrl.research_can_execute() is True
    assert ctrl.recovered_from_enabled is False
    assert ctrl.paused_for_safety is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_operator_pause_does_not_auto_resume() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        resume_live_trading_after_safe_recovery,
    )

    ctrl = reset_live_trading_controller_for_tests()
    op = _op("owner")
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    assert ctrl.transition(op, "PAUSED", confirmed=True, reason="operator") == "PAUSED"
    assert ctrl.recovered_from_enabled is False
    assert ctrl.paused_for_safety is False
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value=_PASS_PROBE_FACTS,
    ), patch(
        "app.application.services.live_trading_control_service.persist_live_trading",
        return_value=True,
    ), patch(
        "app.domain.institutional_trading.operations.control_plane.get_control_plane",
    ):
        assert resume_live_trading_after_safe_recovery() == "PAUSED"
    assert ctrl.research_can_execute() is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_safety_pause_resumes_when_probes_pass() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        apply_fail_closed_from_probes,
        resume_live_trading_after_safe_recovery,
    )

    ctrl = reset_live_trading_controller_for_tests()
    op = _op("owner")
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value={
            "gateway_online": False,
            "mt5_connected": False,
            "mt5_attached": False,
            "ownership": "NOT_OWNED",
        },
    ):
        assert apply_fail_closed_from_probes() == "PAUSED"
    assert ctrl.paused_for_safety is True
    assert ctrl.research_can_execute() is False
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value=_PASS_PROBE_FACTS,
    ), patch(
        "app.application.services.live_trading_control_service.persist_live_trading",
        return_value=True,
    ), patch(
        "app.domain.institutional_trading.operations.control_plane.get_control_plane",
    ):
        assert resume_live_trading_after_safe_recovery() == "ENABLED"
    assert ctrl.research_can_execute() is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_status_reports_activation_blockers() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        build_live_trading_status,
    )

    ctrl = reset_live_trading_controller_for_tests()
    ctrl.hydrate({"live_trading_state": "ENABLED"})
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value={
            "gateway_online": False,
            "mt5_connected": False,
            "mt5_attached": False,
            "ownership": "NOT_OWNED",
            "account_available": False,
        },
    ):
        status = build_live_trading_status()
    assert status["live_trading_state"] == "PAUSED"
    assert status["orders_may_submit"] is False
    assert status["pause_reason"] == "restart_recovery"
    assert "gateway_offline" in status["activation_blockers"]
    assert status["activation_ready"] is False
    assert status["allow_live_promotion"] is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_risk_ceiling_cannot_bypass() -> None:
    cfg = LiveTradingRiskConfig(
        risk_per_trade_pct=Decimal("50"),
        max_daily_loss_pct=Decimal("90"),
        max_open_positions=99,
        allow_martingale=True,
        allow_grid_averaging=True,
        allow_revenge_sizing=True,
    )
    assert cfg.risk_per_trade_pct == HARD_CEILING_RISK_PER_TRADE_PCT
    assert cfg.max_daily_loss_pct == HARD_CEILING_DAILY_LOSS_PCT
    assert cfg.max_open_positions == 2
    assert cfg.allow_martingale is False
    assert cfg.allow_grid_averaging is False
    assert cfg.allow_revenge_sizing is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_account_too_small_for_min_lot() -> None:
    spec = _spec(volume_min=Decimal("0.10"), contract_size=Decimal("100000"))
    result = size_from_broker_specs(
        equity=Decimal("33"),
        risk_pct=Decimal("0.50"),
        stop_distance=Decimal("0.01000"),
        spec=spec,
    )
    assert result.accepted is False
    assert result.reason == ACCOUNT_TOO_SMALL
    decision = evaluate_live_order(
        _req(spec=spec), state="ENABLED", cfg=LiveTradingRiskConfig()
    )
    assert decision.allowed is False
    assert ACCOUNT_TOO_SMALL in decision.reasons or any(
        "too small" in r.lower() for r in decision.reasons
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_size_uses_broker_specs_not_generic_lot() -> None:
    spec = spec_from_broker(
        "XAUUSD",
        {
            "contract_size": "100",
            "volume_min": "0.01",
            "volume_max": "50",
            "volume_step": "0.01",
            "tick_value": "1",
            "tick_size": "0.01",
        },
    )
    assert spec.contract_size == Decimal("100")
    sized = size_from_broker_specs(
        equity=Decimal("33"),
        risk_pct=Decimal("0.50"),
        stop_distance=Decimal("5"),
        spec=spec,
    )
    # 0.50% of $33 = $0.165; loss/lot = 5 * 100 = $500; min lot 0.01 = $5 > budget
    assert sized.accepted is False
    assert sized.reason == ACCOUNT_TOO_SMALL


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.parametrize(
    ("override", "needle"),
    [
        ({"ownership_ok": False}, "broker_ownership"),
        ({"gateway_online": False}, "gateway_offline"),
        ({"mt5_connected": False}, "mt5_disconnected"),
        ({"quote_fresh": False, "quote_age_seconds": Decimal("30")}, "stale"),
        ({"stop_loss": None}, "stop_loss"),
        ({"take_profit": None}, "take_profit"),
        ({"spread": Decimal("9")}, "spread"),
        ({"daily_loss_pct": Decimal("10")}, "daily_loss"),
        ({"consecutive_losses": 5}, "consecutive"),
        ({"open_exposure_pct": Decimal("90")}, "exposure"),
        ({"used_margin": Decimal("20"), "equity": Decimal("33")}, "margin"),
        ({"signal_id": "dup"}, "duplicate_signal"),
        ({"request_id": "dup-order"}, "duplicate_order"),
        ({"market_open": False}, "market_closed"),
        ({"signal_status": "UNSUPPORTED"}, "UNSUPPORTED"),
        ({"oms_healthy": False}, "oms"),
        ({"audit_healthy": False}, "audit"),
        ({"authenticated_authorized": False}, "unauthorized"),
        ({"price_valid": False, "price": None}, "invalid_price"),
        ({"symbol_tradeable": False}, "tradeable"),
    ],
)
def test_pretrade_blocks(override: dict[str, object], needle: str) -> None:
    extra: dict[str, object] = dict(override)
    recent_signals = {"dup"} if extra.get("signal_id") == "dup" else set()
    recent_orders = (
        {"req:dup-order"} if extra.get("request_id") == "dup-order" else set()
    )
    decision = evaluate_live_order(
        _req(**extra),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
        recent_signal_ids=recent_signals,
        recent_order_keys=recent_orders,
    )
    assert decision.allowed is False
    blob = " ".join(decision.reasons).lower()
    assert needle.lower() in blob or needle.lower() in decision.block_code.lower()


@pytest.mark.unit
@pytest.mark.trading_core
def test_disabled_blocks_even_when_signal_is_buy() -> None:
    decision = evaluate_live_order(
        _req(), state="DISABLED", cfg=LiveTradingRiskConfig()
    )
    assert decision.allowed is False
    assert any("live_trading_disabled" in r for r in decision.reasons)


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_fabricated_sl_tp_or_prices() -> None:
    decision = evaluate_live_order(
        _req(
            stop_loss=None, take_profit=None, price=None, entry=None, price_valid=False
        ),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
    )
    assert decision.allowed is False
    reasons = " ".join(decision.reasons)
    assert "stop_loss" in reasons
    assert "take_profit" in reasons


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_martingale_size_increase_after_loss() -> None:
    spec = _spec(
        contract_size=Decimal("1000"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
    )
    # Wide enough stop + tiny contract so 0.01 lots fit $33 * 0.50%.
    decision = evaluate_live_order(
        _req(
            spec=spec,
            stop_loss=Decimal("1.09990"),
            take_profit=Decimal("1.10200"),
            entry=Decimal("1.10000"),
        ),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
        last_loss_volume=Decimal("0.001"),
    )
    assert decision.allowed is False
    assert any("after_loss" in r for r in decision.reasons)


@pytest.mark.unit
@pytest.mark.trading_core
def test_hard_limit_pauses_execution() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    decision = ctrl.evaluate(
        _req(daily_loss_pct=Decimal("10")), apply_side_effects=True
    )
    assert decision.allowed is False
    assert ctrl.snapshot_state() == "PAUSED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_gateway_disconnect_pauses_via_control_plane() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    plane = OperationsControlPlane()
    plane.auto_trading_enabled = True
    plane.auto_trading_run_state = "running"
    plane.mode = plane.mode if hasattr(plane, "mode") else None
    from app.domain.institutional_trading.operations.models import OpsExecutionMode

    plane.mode = OpsExecutionMode.LIVE
    safety = plane.evaluate_auto_trading(_all_pass_facts(gateway_connected=False))
    assert safety.allowed is False
    assert ctrl.snapshot_state() == "PAUSED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_auto_trade_safety_requires_live_trading_enabled() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    blocked = evaluate_auto_trade_safety(
        policy, _all_pass_facts(live_trading_state="DISABLED")
    )
    assert blocked.allowed is False
    ok = evaluate_auto_trade_safety(
        policy, _all_pass_facts(live_trading_state="ENABLED")
    )
    assert ok.allowed is True
    unset = evaluate_auto_trade_safety(
        policy, _all_pass_facts(live_trading_state="UNSET")
    )
    assert unset.allowed is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_strip_secrets() -> None:
    cleaned = strip_secrets(
        {
            "reason": "arm",
            "password": "nope",
            "api_key": "nope",
            "token": "nope",
            "service_role_key": "nope",
        }
    )
    assert "password" not in cleaned
    assert "api_key" not in cleaned
    assert cleaned["reason"] == "arm"


@pytest.mark.unit
@pytest.mark.trading_core
def test_signal_center_defaults_research_can_execute_false() -> None:
    from app.application.services.signal_center_service import _research_can_execute

    assert _research_can_execute() is False
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    assert _research_can_execute() is True


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_admin_api_rejects_trader_for_live_trading() -> None:
    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    with pytest.raises(Exception):
        await dep(user=_user(UserRole.TRADER.value))


@pytest.mark.unit
@pytest.mark.trading_core
def test_live_trading_router_unauthenticated() -> None:
    from app.presentation.routers.live_trading_control import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/live-trading/status")
    assert resp.status_code in {401, 403, 500}


@pytest.mark.unit
@pytest.mark.trading_core
def test_kill_switch_from_enabled() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import kill_live_trading

    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    with (
        patch(
            "app.application.services.live_trading_control_service.persist_live_trading",
            return_value=True,
        ),
        patch(
            "app.application.services.live_trading_control_service.build_live_trading_status",
            return_value={"live_trading_state": "DISABLED"},
        ),
        patch(
            "app.domain.institutional_trading.operations.control_plane.get_control_plane",
        ),
    ):
        out = kill_live_trading(op, confirmed=True, reason="emergency")
    assert ctrl.snapshot_state() == "DISABLED"
    assert ctrl.emergency_latched is True
    assert out["live_trading_state"] == "DISABLED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_audit_failure_blocks_enable() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import arm_live_trading

    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    with (
        patch(
            "app.application.services.live_trading_control_service.persist_live_trading",
            return_value=False,
        ),
        patch(
            "app.application.services.live_trading_control_service._live_probe_facts",
            return_value={
                "account_login_masked": "12••78",
                "broker_server": "Weltrade",
                "gateway_online": True,
                "mt5_connected": True,
                "mt5_attached": True,
                "ownership": "OWNED",
                "account_available": True,
                "equity": Decimal("33"),
                "balance": Decimal("33"),
            },
        ),
        pytest.raises(LiveTradingTransitionError, match="audit_failure"),
    ):
        arm_live_trading(
            op,
            confirmed=True,
            reason="arm",
            confirmation_phrase="I UNDERSTAND THIS USES REAL MONEY",
        )
    assert ctrl.snapshot_state() == "ARMED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_enable_requires_connectivity_and_ownership() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        enable_live_trading,
    )

    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    phrase = "I UNDERSTAND THIS USES REAL MONEY"
    with (
        patch(
            "app.application.services.live_trading_control_service._live_probe_facts",
            return_value={
                "gateway_online": False,
                "mt5_connected": True,
                "mt5_attached": True,
                "ownership": "OWNED",
                "account_available": True,
                "equity": Decimal("33"),
                "balance": Decimal("33"),
            },
        ),
        pytest.raises(LiveTradingTransitionError, match="gateway_offline"),
    ):
        enable_live_trading(op, confirmed=True, reason="go", confirmation_phrase=phrase)
    with (
        patch(
            "app.application.services.live_trading_control_service._live_probe_facts",
            return_value={
                "gateway_online": True,
                "mt5_connected": False,
                "mt5_attached": False,
                "ownership": "OWNED",
                "account_available": True,
                "equity": Decimal("33"),
                "balance": Decimal("33"),
            },
        ),
        pytest.raises(LiveTradingTransitionError, match="mt5_disconnected"),
    ):
        enable_live_trading(op, confirmed=True, reason="go", confirmation_phrase=phrase)
    with (
        patch(
            "app.application.services.live_trading_control_service._live_probe_facts",
            return_value={
                "gateway_online": True,
                "mt5_connected": True,
                "mt5_attached": True,
                "ownership": "NOT_OWNED",
                "account_available": True,
                "equity": Decimal("33"),
                "balance": Decimal("33"),
            },
        ),
        pytest.raises(LiveTradingTransitionError, match="broker_ownership"),
    ):
        enable_live_trading(op, confirmed=True, reason="go", confirmation_phrase=phrase)
    assert ctrl.snapshot_state() == "ARMED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_page_and_nav_keep_trader_free_of_admin() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    page = (root / "frontend/src/app/(app)/admin/page.tsx").read_text(encoding="utf-8")
    nav = (root / "frontend/src/components/layout/nav-config.ts").read_text(
        encoding="utf-8"
    )
    panel = (
        root / "frontend/src/components/ops/live-trading-control-panel.tsx"
    ).read_text(encoding="utf-8")
    assert "/admin/live-trading" in page
    assert "research_can_execute = false" in page
    assert "KILL LIVE TRADING" in panel or "EMERGENCY STOP" in panel
    assert "ARM LIVE TRADING" in panel
    assert "ENABLE LIVE TRADING" in panel
    assert "DISABLE LIVE TRADING" in panel
    assert 'liveConfirmed ? "ACTIVE"' in panel
    assert "ACTIVE" in panel
    assert "OPERATOR_RAIL_ORDER = TRADER_DESK_ORDER" in nav
    assert (
        '"/admin/live-trading"' in nav
        or "'/admin/live-trading'" in nav
        or "/admin/live-trading" in nav
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_safe_size_accepted_when_min_lot_fits_risk() -> None:
    spec = _spec(
        contract_size=Decimal("10"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        tick_value=None,
        tick_size=None,
    )
    sized = size_from_broker_specs(
        equity=Decimal("33"),
        risk_pct=Decimal("0.50"),
        stop_distance=Decimal("0.10"),
        spec=spec,
    )
    assert sized.accepted is True
    assert sized.volume >= Decimal("0.01")
    decision = evaluate_live_order(
        _req(
            spec=spec,
            stop_loss=Decimal("1.09900"),
            entry=Decimal("1.10000"),
            take_profit=Decimal("1.10200"),
        ),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
    )
    # 0.001 stop * contract 10 = 0.01/lot; min lot is inside $0.165.
    assert decision.allowed is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_neutral_none_stale_not_executed() -> None:
    for status in (
        "NEUTRAL",
        "NONE",
        "STALE",
        "DATA_UNAVAILABLE",
        "MARKET_CLOSED",
        "FAILED",
        "UNSUPPORTED",
    ):
        decision = evaluate_live_order(
            _req(signal_status=status),
            state="ENABLED",
            cfg=LiveTradingRiskConfig(),
        )
        assert decision.allowed is False, status


@pytest.mark.unit
@pytest.mark.trading_core
def test_invalid_volume_and_nan_price_blocked() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        orders_may_submit,
        public_state_name,
    )

    bad_vol = evaluate_live_order(
        _req(requested_volume=Decimal("0")),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
    )
    assert bad_vol.allowed is False
    assert any("volume" in r for r in bad_vol.reasons)
    nan = evaluate_live_order(
        _req(price=Decimal("NaN"), price_valid=True),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
    )
    assert nan.allowed is False
    inf = evaluate_live_order(
        _req(entry=Decimal("Infinity")),
        state="ENABLED",
        cfg=LiveTradingRiskConfig(),
    )
    assert inf.allowed is False
    assert orders_may_submit("LIVE_ENABLED") is True
    assert orders_may_submit("DISABLED") is False
    assert public_state_name("ENABLED") == "LIVE_ENABLED"
    assert public_state_name("DISABLED", activation_ready=True) == "READY_FOR_REVIEW"


@pytest.mark.unit
@pytest.mark.trading_core
def test_arm_blocked_when_broker_or_gateway_unhealthy() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import arm_live_trading

    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    phrase = "I UNDERSTAND THIS USES REAL MONEY"
    cases = [
        ({"gateway_online": False}, "gateway_offline"),
        ({"mt5_connected": False, "mt5_attached": False}, "mt5_disconnected"),
        ({"ownership": "NOT_OWNED"}, "broker_ownership"),
        ({"equity": None, "balance": None}, "equity_unavailable"),
    ]
    base = {
        "gateway_online": True,
        "mt5_connected": True,
        "mt5_attached": True,
        "ownership": "OWNED",
        "account_available": True,
        "equity": Decimal("33"),
        "balance": Decimal("33"),
    }
    for extra, needle in cases:
        facts = {**base, **extra}
        with (
            patch(
                "app.application.services.live_trading_control_service._live_probe_facts",
                return_value=facts,
            ),
            pytest.raises(LiveTradingTransitionError, match=needle),
        ):
            arm_live_trading(
                op, confirmed=True, reason="arm", confirmation_phrase=phrase
            )
        assert ctrl.snapshot_state() == "DISABLED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_emergency_stop_from_any_state_disables() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    assert ctrl.emergency_disable(op, reason="panic") == "DISABLED"
    assert ctrl.research_can_execute() is False
    assert ctrl.emergency_latched is True
    decision = evaluate_live_order(
        _req(), state=ctrl.snapshot_state(), cfg=LiveTradingRiskConfig()
    )
    assert decision.allowed is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_disable_from_enabled_and_live_alias_safety() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    assert ctrl.transition(op, "DISABLED", confirmed=True, reason="off") == "DISABLED"
    assert ctrl.research_can_execute() is False
    ok = evaluate_auto_trade_safety(
        AutoTradePolicy(enabled=True, run_state="running"),
        _all_pass_facts(live_trading_state="LIVE_ENABLED"),
    )
    assert ok.allowed is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_allow_live_promotion_never_true() -> None:
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        build_live_trading_status,
    )

    reset_live_trading_controller_for_tests()
    with patch(
        "app.application.services.live_trading_control_service._live_probe_facts",
        return_value={
            "gateway_online": False,
            "mt5_connected": False,
            "ownership": "NOT_OWNED",
        },
    ):
        status = build_live_trading_status()
    assert status["live_trading_state"] == "DISABLED"
    assert status["research_can_execute"] is False
    assert status["allow_live_promotion"] is False
    assert status["orders_may_submit"] is False
    assert ALLOW_LIVE_PROMOTION is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_adapter_account_fill_does_not_invent_numbers() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.application.services.live_trading_control_service import (
        _fill_from_adapter_account,
        _pick_int_login,
    )

    assert _pick_int_login(None, "0", 1, 247001) == 247001
    assert _pick_int_login(None, 0, 1) == 0

    class _Adapter:
        def account_info(self) -> SimpleNamespace:
            return SimpleNamespace(
                login=247001,
                balance="33.12",
                equity="33.05",
                free_margin="32.80",
                margin="0.25",
                margin_level="13220",
                server="Weltrade-Demo",
            )

    runtime = SimpleNamespace(probes=SimpleNamespace(mt5_adapter=_Adapter()))
    out: dict[str, object] = {}
    with patch(
        "app.application.services.institutional_ite_runtime.get_ite_runtime",
        return_value=runtime,
    ):
        _fill_from_adapter_account(out)
    assert out["account_login"] == 247001
    assert out["balance"] == Decimal("33.12")
    assert out["equity"] == Decimal("33.05")
    assert out["account_available"] is True
    empty: dict[str, object] = {}
    with patch(
        "app.application.services.institutional_ite_runtime.get_ite_runtime",
        return_value=SimpleNamespace(probes=SimpleNamespace(mt5_adapter=None)),
    ):
        _fill_from_adapter_account(empty)
    assert empty == {}


@pytest.mark.unit
@pytest.mark.trading_core
def test_session_cache_login_does_not_call_account_info() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from app.application.services.live_trading_control_service import (
        _fill_from_session_cache,
    )

    adapter = MagicMock()
    runtime = SimpleNamespace(probes=SimpleNamespace(mt5_adapter=adapter))
    out: dict[str, object] = {}
    with (
        patch(
            "app.application.services.institutional_ite_runtime.get_ite_runtime",
            return_value=runtime,
        ),
        patch(
            "app.application.services.mt5_session_guard._live_account_login",
            return_value=247001,
        ),
    ):
        _fill_from_session_cache(out)
    assert out["account_login"] == 247001
    adapter.account_info.assert_not_called()
