"""Unit tests for production trading-component health derivation."""

from __future__ import annotations

from app.application.services.production_component_health import (
    derive_ai_status,
    derive_oms_status,
)


def test_oms_healthy_when_live_path_ready() -> None:
    result = derive_oms_status(
        execution_enabled=True,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=False,
    )
    assert result.status == "HEALTHY"


def test_oms_not_ready_when_mock() -> None:
    result = derive_oms_status(
        execution_enabled=True,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=True,
    )
    assert result.status == "NOT_READY"
    assert "mt5_use_mock" in result.detail


def test_oms_disabled_when_execution_off() -> None:
    result = derive_oms_status(
        execution_enabled=False,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=False,
    )
    assert result.status == "DISABLED"


def test_ai_healthy_only_with_runtime() -> None:
    assert derive_ai_status(ite_runtime_present=True).status == "HEALTHY"
    missing = derive_ai_status(ite_runtime_present=False)
    assert missing.status == "NOT_READY"
    assert "ite_runtime" in missing.detail
