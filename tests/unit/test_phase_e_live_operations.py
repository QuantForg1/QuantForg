"""Phase E — live operations reliability: gateway recovery mapping + evidence."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.application.services.launch_readiness import build_launch_readiness
from app.application.services.live_ops_evidence import build_live_ops_evidence
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from app.domain.institutional_trading.reliability.health import ProbeInputs


def _probes(*, gateway: bool, mt5: bool) -> ProbeInputs:
    return ProbeInputs(
        gateway_latency_ms=12.0 if gateway else 1074.0,
        gateway_available=gateway,
        mt5_connected=mt5,
        cloudflare_tunnel_up=gateway,
    )


def _patch(*, execution_enabled: bool, gateway: bool, mt5: bool, market: bool):
    settings = MagicMock()
    settings.execution_enabled = execution_enabled
    settings.mt5_gateway_base_url = "https://gateway.quantforg.com"
    settings.mt5_use_mock = False
    collector = MagicMock()
    collector.collect.return_value = _probes(gateway=gateway, mt5=mt5)
    collector.mt5_adapter = None
    enrich = {
        "account_trading_enabled": True if mt5 else None,
        "mt5_autotrading_enabled": True if mt5 else None,
        "symbol_tradable": True if mt5 else None,
        "no_broker_restrictions": True if mt5 else None,
        "market_data_live": (
            False if not market else (True if gateway and mt5 else None)
        ),
        "margin_available": True if mt5 else None,
        "spread": Decimal("0.35") if market and mt5 else None,
        "session": "london" if market else None,
        "health_payload": None,
    }
    return (
        patch(
            "app.application.services.auto_trading_status._probe_collector",
            return_value=collector,
        ),
        patch(
            "app.application.services.auto_trading_status._enrich_from_adapter",
            return_value=enrich,
        ),
        settings,
    )


@pytest.fixture(autouse=True)
def _reset_phase_a() -> None:
    reset_phase_a_plane_for_tests()
    yield
    reset_phase_a_plane_for_tests()


@pytest.mark.unit
class TestPhaseELaunchLockMapping:
    def test_gateway_down_only_gateway_blocks_execution(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.LIVE
        p1, p2, settings = _patch(
            execution_enabled=True, gateway=False, mt5=False, market=False
        )
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=True
            )
        exec_keys = [i.key for i in report.items if not i.passed and i.blocks_execution]
        assert exec_keys == ["gateway"]
        assert report.execution_block_code == "GATEWAY_OFFLINE"
        assert report.first_blocking_lock is not None
        assert report.first_blocking_lock["key"] == "gateway"
        broker = next(i for i in report.items if i.key == "broker")
        assert broker.blocks_execution is False
        assert "credential" in broker.why.lower()
        assert broker.canonical_state == "GATEWAY_UNAVAILABLE"
        market = next(i for i in report.items if i.key == "market_open")
        assert market.blocks_execution is False
        why = market.why.lower()
        assert "market-hours" in why or "not evaluated" in why
        owner = next(i for i in report.items if i.key == "owner_authorization")
        assert owner.category == "AUTH"
        assert owner.blocks_execution is False

    def test_broker_down_only_broker_family_blocks_when_gateway_up(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.LIVE
        p1, p2, settings = _patch(
            execution_enabled=True, gateway=True, mt5=False, market=False
        )
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=True
            )
        gw = next(i for i in report.items if i.key == "gateway")
        assert gw.passed is True
        exec_keys = [i.key for i in report.items if not i.passed and i.blocks_execution]
        assert "gateway" not in exec_keys
        assert "broker" in exec_keys
        broker = next(i for i in report.items if i.key == "broker")
        assert broker.canonical_state == "DISCONNECTED"
        assert broker.execution_code == "BROKER_DISCONNECTED"
        market = next(i for i in report.items if i.key == "market_open")
        assert market.blocks_execution is False

    def test_market_no_quote_does_not_become_gateway_unavailable(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.LIVE
        p1, p2, settings = _patch(
            execution_enabled=True, gateway=True, mt5=True, market=False
        )
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=True
            )
        gw = next(i for i in report.items if i.key == "gateway")
        broker = next(i for i in report.items if i.key == "broker")
        market = next(i for i in report.items if i.key == "market_open")
        assert gw.passed is True
        assert broker.passed is True
        assert market.passed is False
        assert market.blocks_execution is True
        assert market.execution_code == "NO_QUOTE"
        assert market.canonical_state != "GATEWAY_UNAVAILABLE"


@pytest.mark.unit
class TestPhaseEReadOnlyEvidence:
    def test_evidence_has_no_oms_authority_and_scrubs_secrets(self) -> None:
        plane = OperationsControlPlane()
        p1, p2, settings = _patch(
            execution_enabled=True, gateway=True, mt5=True, market=True
        )
        with (
            p1,
            p2,
            patch(
                "app.application.services.live_ops_evidence.collect_trading_component_health",
                create=True,
            ),
            patch(
                "app.application.services.production_component_health.collect_trading_component_health",
                return_value={
                    "statuses": {
                        "gateway": "HEALTHY",
                        "mt5": "CONNECTED",
                        "oms": "HEALTHY",
                        "ai": "HEALTHY",
                    },
                    "timing": {"total_ms": 12},
                    "all_ready_for_limited_pilot": True,
                },
            ),
        ):
            payload = build_live_ops_evidence(plane, settings=settings)
        assert payload["read_only"] is True
        assert payload["oms_authority"] is False
        assert payload["mt5_order_authority"] is False
        assert payload["mutations_allowed"] is False
        assert payload["auth"]["mechanism"] == "bearer"
        assert payload["auth"]["session_key"] == "qf_access_token"
        blob = str(payload).lower()
        assert "eyj" not in blob
        assert "password" not in payload
        assert "access_token" not in payload


@pytest.mark.unit
class TestPhaseEOutageDoesNotWeakenSafety:
    def test_gateway_outage_does_not_clear_kill_or_risk(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.LIVE
        p1, p2, settings = _patch(
            execution_enabled=True, gateway=False, mt5=False, market=False
        )
        with p1, p2:
            report = build_launch_readiness(
                plane, settings=settings, owner_authorized=True
            )
        kill = next(i for i in report.items if i.key == "kill_switch")
        risk = next(i for i in report.items if i.key == "risk_lock")
        assert kill.passed is True
        assert risk.passed is True
        assert report.ready_for_gate_enabled is False

    def test_auto_trade_facts_block_new_entry_when_gateway_down(self) -> None:
        plane = OperationsControlPlane()
        plane.mode = OpsExecutionMode.LIVE
        facts = AutoTradeLiveFacts(
            gateway_connected=False,
            broker_connected=False,
            market_data_live=False,
            risk_engine_pass=True,
            account_trading_enabled=True,
            mt5_autotrading_enabled=True,
            symbol="XAUUSD",
            symbol_tradable=True,
            margin_available=True,
            no_broker_restrictions=True,
            execution_enabled=True,
            ops_mode="LIVE",
        )
        plane.auto_trading_enabled = True
        plane.auto_trading_run_state = "running"
        safety = plane.evaluate_auto_trading(facts)
        assert safety.allowed is False
        keys = [c.key for c in safety.conditions if not c.passed]
        assert "gateway_connected" in keys
