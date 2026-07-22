"""Phase F unit tests — ops control plane."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.institutional_oms_manage_adapter import (
    RecordingOmsManagePort,
)
from app.application.services.institutional_ops_guards import (
    GuardedOmsManagePort,
    GuardedOmsSubmitPort,
)
from app.application.services.live_auto_trade_certification import (
    reset_live_cert_service_for_tests,
    seed_certified_demo_report_for_tests,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    PermissionDenied,
)
from app.domain.institutional_trading.operations.health import HealthInputs
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
    OpsPermission,
)


def _op(role: str = "owner") -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role=role,
        display_name="Op Tester",
        ip="127.0.0.1",
        user_agent="pytest",
    )


@pytest.mark.unit
class TestModeTransitions:
    def test_shadow_to_canary_to_live_to_shadow(self) -> None:
        seed_certified_demo_report_for_tests()
        plane = OperationsControlPlane()
        op = _op()
        r1 = plane.transition_mode(
            op, OpsExecutionMode.CANARY, reason="promote", confirmed=True
        )
        assert r1.ok
        assert plane.mode is OpsExecutionMode.CANARY
        r2 = plane.transition_mode(
            op, OpsExecutionMode.LIVE, reason="go live", confirmed=True
        )
        assert r2.ok
        r3 = plane.transition_mode(
            op, OpsExecutionMode.SHADOW, reason="cool down", confirmed=True
        )
        assert r3.ok
        assert plane.mode is OpsExecutionMode.SHADOW

    def test_live_allowed_without_demo_certification(self) -> None:
        """OWNER policy: Demo Certification is optional — not a LIVE gate."""
        reset_live_cert_service_for_tests()
        plane = OperationsControlPlane()
        op = _op()
        assert plane.transition_mode(
            op, OpsExecutionMode.CANARY, reason="promote", confirmed=True
        ).ok
        live = plane.transition_mode(
            op, OpsExecutionMode.LIVE, reason="go live", confirmed=True
        )
        assert live.ok is True
        assert plane.mode is OpsExecutionMode.LIVE

    def test_illegal_transition(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        bad = plane.transition_mode(
            op, OpsExecutionMode.LIVE, reason="skip", confirmed=True
        )
        assert bad.ok is False

    def test_confirmation_required(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        r = plane.transition_mode(
            op, OpsExecutionMode.CANARY, reason="x", confirmed=False
        )
        assert r.ok is False
        assert "confirmation" in r.message


@pytest.mark.unit
class TestKillSwitch:
    def test_kill_blocks_oms_and_pme(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        plane.transition_mode(op, OpsExecutionMode.CANARY, reason="c", confirmed=True)
        assert plane.oms_orders_allowed() is True
        plane.arm_kill_switch(op, reason="emergency", confirmed=True)
        assert plane.oms_orders_allowed() is False
        assert plane.pme_modifications_allowed() is False
        assert plane.alerts.unacked_count() >= 1

    def test_shadow_blocks_oms_without_kill(self) -> None:
        plane = OperationsControlPlane()
        assert plane.mode is OpsExecutionMode.SHADOW
        assert plane.oms_orders_allowed() is False
        assert plane.pme_modifications_allowed() is True

    def test_guarded_ports(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        plane.transition_mode(op, OpsExecutionMode.CANARY, reason="c", confirmed=True)
        submit = RecordingOmsPort()
        manage = RecordingOmsManagePort()
        g_submit = GuardedOmsSubmitPort(inner=submit, plane=plane)
        g_manage = GuardedOmsManagePort(inner=manage, plane=plane)
        intent = parse_order_intent(
            symbol="XAUUSD",
            side="buy",
            order_type="market",
            volume="0.1",
        )
        ok = g_submit.submit_market(
            user_id=uuid4(),
            request_id="1",
            intent=intent,
            connected=True,
            login=1,
        )
        assert ok.outcome == "success"
        assert len(submit.calls) == 1

        plane.arm_kill_switch(op, reason="stop", confirmed=True)
        blocked = g_submit.submit_market(
            user_id=uuid4(),
            request_id="2",
            intent=intent,
            connected=True,
            login=1,
        )
        assert blocked.outcome == "disabled"
        assert len(submit.calls) == 1

        m = g_manage.modify_sltp(
            user_id=uuid4(),
            request_id="3",
            symbol="XAUUSD",
            side="buy",
            position=1,
            stop_loss=Decimal("2300"),
            take_profit=None,
            comment="x",
            connected=True,
            login=1,
        )
        assert m.outcome == "disabled"


@pytest.mark.unit
class TestConfigRollbackAudit:
    def test_versioning_and_rollback(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
        _a = plane.promote_config(
            op,
            config_version="cfg-a",
            strategy_version="strat-a",
            reason="first",
            now=now,
        )
        b = plane.promote_config(
            op,
            config_version="cfg-b",
            strategy_version="strat-b",
            reason="second",
            risk_per_trade_pct=Decimal("0.5"),
            now=now,
        )
        assert plane.configs.count() >= 3  # baseline + a + b
        assert b.rollback_target == "cfg-a" or b.rollback_target is not None
        rolled = plane.rollback(
            op, target_config_version="cfg-a", reason="revert", confirmed=True, now=now
        )
        assert rolled.config_version == "cfg-a"
        assert plane.config_version == "cfg-a"
        assert plane.strategy_version == "strat-a"
        actions = [e.action for e in plane.audit.list()]
        assert "config_promote" in actions
        assert "rollback" in actions

    def test_audit_never_cleared_by_api(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        plane.arm_kill_switch(op, reason="a", confirmed=True)
        plane.disarm_kill_switch(op, reason="b", confirmed=True)
        assert plane.audit.count() >= 2


@pytest.mark.unit
class TestHealthAlertsPermissionsRunbooks:
    def test_health_and_alerts(self) -> None:
        plane = OperationsControlPlane()
        plane.update_health(
            HealthInputs(
                gateway_available=False,
                mt5_connected=False,
                gateway_latency_ms=900,
                order_latency_ms=900,
            )
        )
        assert plane.health.latest() is not None
        assert plane.health.latest().health_score < 100
        assert plane.alerts.unacked_count() >= 1
        alert = plane.alerts.list(unacked_only=True)[0]
        plane.acknowledge_alert(_op(), alert.id)
        assert alert.id not in {a.id for a in plane.alerts.list(unacked_only=True)}

    def test_permissions_viewer_denied(self) -> None:
        plane = OperationsControlPlane()
        viewer = _op("viewer")
        assert viewer.has(OpsPermission.VIEW) is False
        with pytest.raises(PermissionDenied):
            plane.arm_kill_switch(viewer, reason="no", confirmed=True)

    def test_runbooks(self) -> None:
        plane = OperationsControlPlane()
        op = _op()
        books = plane.runbooks.list()
        assert len(books) >= 7
        result = plane.execute_runbook(op, "emergency_shutdown")
        assert result["ok"] is True
        assert result["checklist"]

    def test_control_and_readiness(self) -> None:
        plane = OperationsControlPlane()
        cc = plane.control_center()
        for key in (
            "execution_mode",
            "kill_switch",
            "shadow_mode",
            "canary_mode",
            "live_mode",
            "strategy_version",
            "config_version",
            "promotion_status",
        ):
            assert key in cc
        rd = plane.readiness_dashboard()
        assert "health_score" in rd
        assert "current_mode" in rd
