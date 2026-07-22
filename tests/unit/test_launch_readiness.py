"""Unit tests — OWNER launch readiness audit + official promotion sequence."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.services.launch_readiness import (
    build_launch_readiness,
    promote_to_live_execution,
)
from app.application.services.live_auto_trade_certification import (
    reset_live_cert_service_for_tests,
    seed_certified_demo_report_for_tests,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.institutional_trading.reliability.health import ProbeInputs


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Launch Owner",
    )


def _green_probes() -> ProbeInputs:
    return ProbeInputs(
        gateway_latency_ms=8.0,
        gateway_available=True,
        mt5_connected=True,
        cloudflare_tunnel_up=True,
    )


def _patch_status(*, execution_enabled: bool):
    settings = MagicMock()
    settings.execution_enabled = execution_enabled
    settings.mt5_gateway_base_url = "https://gateway.example"
    collector = MagicMock()
    collector.collect.return_value = _green_probes()
    collector.mt5_adapter = None
    return (
        patch(
            "app.application.services.auto_trading_status._probe_collector",
            return_value=collector,
        ),
        patch(
            "app.application.services.auto_trading_status._enrich_from_adapter",
            return_value={
                "account_trading_enabled": True,
                "mt5_autotrading_enabled": True,
                "symbol_tradable": True,
                "no_broker_restrictions": True,
                "market_data_live": True,
                "margin_available": True,
                "spread": Decimal("0.35"),
                "session": "london",
                "health_payload": None,
            },
        ),
        settings,
    )


@pytest.mark.unit
class TestLaunchReadiness:
    def test_reports_why_and_how_when_shadow(self) -> None:
        plane = OperationsControlPlane()
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=False)
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=False
            )
        assert report.ready_for_promotion is False
        assert report.next_promotion_target == "CANARY"
        keys = {b["key"] for b in report.blockers}
        assert "execution_enabled" in keys
        assert "owner_authorization" in keys
        assert "demo_certification" not in keys
        assert report.ready_for_canary is False
        assert report.ready_for_live is False
        exec_item = next(i for i in report.items if i.key == "execution_enabled")
        assert "EXECUTION_ENABLED" in exec_item.why
        assert "Railway" in exec_item.how_to_resolve
        demo = next(i for i in report.items if i.key == "demo_certification")
        assert demo.required_for_live is False
        assert demo.required_for_promotion is False
        assert "OPTIONAL" in demo.value or "Optional" in demo.how_to_resolve
        mode = next(i for i in report.items if i.key == "ops_mode")
        assert "SHADOW" in mode.how_to_resolve and "CANARY" in mode.how_to_resolve
        assert "LIVE" in mode.how_to_resolve

    def test_shadow_ready_without_demo_cert(self) -> None:
        plane = OperationsControlPlane()
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=True)
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=True
            )
        assert report.demo_certified is False
        assert report.ready_for_canary is True
        assert report.ready_for_live is True
        assert report.ready_for_promotion is True
        assert report.next_promotion_target == "LIVE"
        assert report.to_dict()["demo_certification_required_for_live"] is False

    def test_refuses_promotion_without_confirmation(self) -> None:
        plane = OperationsControlPlane()
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=True)
        with p1, p2:
            out = promote_to_live_execution(
                plane,
                _op(),
                reason="test",
                confirmed=False,
                settings=settings,
            )
        assert out["ok"] is False
        assert plane.mode is OpsExecutionMode.SHADOW

    def test_refuses_promotion_when_execution_disabled(self) -> None:
        plane = OperationsControlPlane()
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=False)
        with p1, p2:
            out = promote_to_live_execution(
                plane,
                _op(),
                reason="test",
                confirmed=True,
                settings=settings,
            )
        assert out["ok"] is False
        assert out["promoted"] is False
        assert plane.mode is OpsExecutionMode.SHADOW
        assert out["readiness"]["ready_for_canary"] is False

    def test_promotes_to_live_without_demo_cert(self) -> None:
        plane = OperationsControlPlane()
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=True)
        with p1, p2:
            out = promote_to_live_execution(
                plane,
                _op(),
                reason="OWNER policy — Demo cert optional",
                confirmed=True,
                settings=settings,
            )
        assert plane.mode is OpsExecutionMode.LIVE
        assert out["promoted"] is True
        assert any(s.get("to") == "CANARY" for s in out["steps"])
        assert any(s.get("to") == "LIVE" for s in out["steps"])
        assert plane.auto_trading_run_state == "running"

    def test_canary_to_live_without_demo_cert(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.CANARY
        reset_live_cert_service_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=True)
        with p1, p2:
            out = promote_to_live_execution(
                plane,
                _op(),
                reason="OWNER go live",
                confirmed=True,
                settings=settings,
            )
        assert plane.mode is OpsExecutionMode.LIVE
        assert out["promoted"] is True

    def test_official_shadow_canary_live_when_ready(self) -> None:
        plane = OperationsControlPlane()
        seed_certified_demo_report_for_tests()
        p1, p2, settings = _patch_status(execution_enabled=True)
        with p1, p2:
            out = promote_to_live_execution(
                plane,
                _op(),
                reason="OWNER launch",
                confirmed=True,
                settings=settings,
            )
        assert plane.mode is OpsExecutionMode.LIVE
        assert out["promoted"] is True
        assert any(s.get("to") == "CANARY" for s in out["steps"])
        assert any(s.get("to") == "LIVE" for s in out["steps"])
        assert plane.auto_trading_run_state == "running"
        for step in out["steps"]:
            if step.get("action") == "mode_transition":
                assert not (
                    step.get("from") == "SHADOW" and step.get("to") == "LIVE"
                )

    def test_never_jumps_shadow_to_live_directly(self) -> None:
        plane = OperationsControlPlane()
        assert plane.mode is OpsExecutionMode.SHADOW
        result = plane.transition_mode(
            _op(), OpsExecutionMode.LIVE, reason="illegal", confirmed=True
        )
        assert result.ok is False
        assert plane.mode is OpsExecutionMode.SHADOW
