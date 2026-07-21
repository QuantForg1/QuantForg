"""Live Auto Trading certification — fail-closed; no fabricated fills."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.live_auto_trade_certification import (
    LiveAutoTradeCertificationService,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
)
from app.domain.institutional_trading.live_certification import (
    DEMO_CERT_VOLUME,
    LiveTradeEvidence,
    build_stage_results,
    certify_or_stop,
    evaluate_live_cert_checklist,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity


def _op() -> OperatorIdentity:
    return OperatorIdentity(user_id=uuid4(), role="owner", display_name="cert")


def _pass_facts(**overrides: object) -> AutoTradeLiveFacts:
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
def test_checklist_stops_when_gateway_down() -> None:
    result = evaluate_live_cert_checklist(
        facts=_pass_facts(gateway_connected=False),
        policy=AutoTradePolicy(enabled=True),
        mt5_logged_in=True,
        exposure_pass=True,
        drawdown_pass=True,
        account_is_demo=True,
    )
    assert result.ready is False
    assert any("Gateway" in r for r in result.failed_reasons)


@pytest.mark.unit
def test_certify_stops_without_trade_evidence() -> None:
    checklist = evaluate_live_cert_checklist(
        facts=_pass_facts(),
        policy=AutoTradePolicy(enabled=True),
        mt5_logged_in=True,
        exposure_pass=True,
        drawdown_pass=True,
        account_is_demo=True,
    )
    assert checklist.ready is True
    report = certify_or_stop(checklist=checklist, trade=None)
    assert report.certified is False
    assert report.status == "NOT_CERTIFIED"
    assert report.mode_auto_switched is False
    assert "not simulated" in (report.failure_reason or "").lower() or (
        "No real broker trade evidence" in (report.failure_reason or "")
    )


@pytest.mark.unit
def test_certify_rejects_non_demo_volume() -> None:
    checklist = evaluate_live_cert_checklist(
        facts=_pass_facts(),
        policy=AutoTradePolicy(enabled=True),
        mt5_logged_in=True,
        exposure_pass=True,
        drawdown_pass=True,
        account_is_demo=True,
    )
    trade = LiveTradeEvidence(
        broker="Weltrade",
        account_type="Demo",
        symbol="XAUUSD",
        volume=Decimal("0.10"),
        ticket=1,
        deal=2,
        entry=Decimal("2300"),
        exit=Decimal("2301"),
        profit_loss=Decimal("1"),
        execution_latency_ms=12.0,
        margin_used=Decimal("10"),
        risk_pct=Decimal("1"),
        audit_id="aud-1",
        position_closed=True,
        history_recorded=True,
        analytics_recorded=True,
    )
    stages = build_stage_results(
        completed=dict.fromkeys(
            (
                "signal",
                "risk_check",
                "order_check",
                "order_send",
                "broker_fill",
                "position_open",
                "position_close",
                "execution_audit",
                "history",
                "analytics",
            ),
            True,
        )
    )
    report = certify_or_stop(checklist=checklist, stages=stages, trade=trade)
    assert report.certified is False
    assert str(DEMO_CERT_VOLUME) in (report.failure_reason or "")


@pytest.mark.unit
def test_certify_requires_execution_metrics() -> None:
    checklist = evaluate_live_cert_checklist(
        facts=_pass_facts(),
        policy=AutoTradePolicy(enabled=True),
        mt5_logged_in=True,
        exposure_pass=True,
        drawdown_pass=True,
        account_is_demo=True,
    )
    trade = LiveTradeEvidence(
        broker="Weltrade",
        account_type="Demo",
        symbol="XAUUSD",
        volume=DEMO_CERT_VOLUME,
        ticket=1,
        deal=2,
        entry=Decimal("2300"),
        exit=Decimal("2301"),
        profit_loss=Decimal("1"),
        execution_latency_ms=12.0,
        margin_used=Decimal("10"),
        risk_pct=Decimal("1"),
        audit_id="aud-1",
        position_closed=True,
        history_recorded=True,
        analytics_recorded=True,
    )
    stages = build_stage_results(
        completed=dict.fromkeys(
            (
                "signal",
                "risk_check",
                "order_check",
                "order_send",
                "broker_fill",
                "position_open",
                "position_close",
                "execution_audit",
                "history",
                "analytics",
            ),
            True,
        )
    )
    report = certify_or_stop(checklist=checklist, stages=stages, trade=trade)
    assert report.certified is False
    assert "signal_time_ms" in (report.failure_reason or "")


@pytest.mark.unit
def test_mode_never_auto_switches_on_cert() -> None:
    plane = OperationsControlPlane()
    assert plane.mode.value == "SHADOW"
    svc = LiveAutoTradeCertificationService(plane=plane)
    report = svc.run_certification_attempt(
        _op(),
        facts=_pass_facts(),
        mt5_logged_in=True,
        exposure_pass=True,
        drawdown_pass=True,
        account_is_demo=True,
        trade=None,
        reason="no trade",
    )
    assert report.mode_auto_switched is False
    assert plane.mode.value == "SHADOW"


@pytest.mark.unit
def test_service_disables_auto_trading_on_failure() -> None:
    plane = OperationsControlPlane()
    op = _op()
    plane.update_auto_trade_controls(op, enabled=True, reason="arm for test")
    assert plane.auto_trading_enabled is True

    svc = LiveAutoTradeCertificationService(plane=plane)
    report = svc.run_certification_attempt(
        op,
        facts=_pass_facts(gateway_connected=False),
        mt5_logged_in=False,
        exposure_pass=False,
        drawdown_pass=False,
        account_is_demo=False,
        trade=None,
        reason="probe failure",
    )
    assert report.certified is False
    assert report.status == "STOPPED"
    assert plane.auto_trading_enabled is False
    assert report.mode_auto_switched is False
    assert plane.mode.value == "SHADOW"
