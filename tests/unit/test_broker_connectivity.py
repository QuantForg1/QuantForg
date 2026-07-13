"""Unit tests for Broker Connectivity Framework."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services.broker_connectivity import BrokerConnectivityService
from app.domain.broker_connectivity.matrix import CAPABILITY_MATRIX, profile_for
from app.domain.broker_connectivity.types import (
    ConnectivityCapability,
    ConnectivityStatus,
)
from app.infrastructure.brokers.connectivity.mt5 import MT5ConnectivityAdapter
from app.infrastructure.brokers.connectivity.unsupported import (
    UnsupportedBrokerAdapter,
    default_unsupported_adapters,
)


@pytest.mark.unit
class TestCapabilityMatrix:
    def test_mt5_implemented_others_not(self) -> None:
        mt5 = profile_for("mt5")
        assert mt5 is not None
        assert mt5.implemented is True
        assert ConnectivityCapability.HEALTH in mt5.capabilities

        for p in CAPABILITY_MATRIX:
            if p.platform == "mt5":
                continue
            assert p.implemented is False
            assert p.capabilities == ()

    def test_required_venues_present(self) -> None:
        codes = {p.platform for p in CAPABILITY_MATRIX}
        for expected in (
            "mt5",
            "ctrader",
            "interactive_brokers",
            "binance",
            "bybit",
            "okx",
            "oanda",
            "fxcm",
            "alpaca",
        ):
            assert expected in codes


@pytest.mark.unit
class TestUnsupportedAdapters:
    def test_clean_unsupported(self) -> None:
        adapter = UnsupportedBrokerAdapter("binance")
        result = adapter.health()
        assert result.status is ConnectivityStatus.UNSUPPORTED
        assert "not implemented" in result.reason.lower()
        assert result.data is None

    def test_capabilities_returns_declared_matrix(self) -> None:
        adapter = UnsupportedBrokerAdapter("oanda")
        result = adapter.capabilities()
        assert result.status is ConnectivityStatus.OK
        assert isinstance(result.data, dict)
        assert result.data["implemented"] is False

    def test_default_stubs_cover_future_venues(self) -> None:
        stubs = default_unsupported_adapters()
        assert len(stubs) == 8
        assert all(
            s.connect({}).status is ConnectivityStatus.UNSUPPORTED for s in stubs
        )


@pytest.mark.unit
class TestMT5ConnectivityAdapter:
    def _mock_mt5(self, *, connected: bool = False) -> MagicMock:
        mt5 = MagicMock()
        mt5._live_session_ref = "sess-1" if connected else None
        mt5.client = SimpleNamespace(is_connected=connected)
        mt5.is_live_session.return_value = connected
        mt5.execution_enabled = False
        return mt5

    def test_health_unavailable_when_disconnected(self) -> None:
        adapter = MT5ConnectivityAdapter(self._mock_mt5(connected=False))
        result = adapter.health()
        assert result.status is ConnectivityStatus.UNAVAILABLE
        assert result.platform == "mt5"

    def test_health_ok_when_connected(self) -> None:
        mt5 = self._mock_mt5(connected=True)
        mt5.health.return_value = SimpleNamespace(
            connected=True,
            latency_ms=11.5,
            server="Demo",
            login_status="ok",
            terminal_build=4000,
            version="5.0",
            last_heartbeat_at="2026-01-01T00:00:00+00:00",
        )
        adapter = MT5ConnectivityAdapter(mt5)
        result = adapter.health()
        assert result.status is ConnectivityStatus.OK
        assert result.data["server"] == "Demo"
        assert result.latency_ms is not None

    def test_trading_never_order_send(self) -> None:
        mt5 = self._mock_mt5(connected=True)
        adapter = MT5ConnectivityAdapter(mt5)
        result = adapter.trading({"symbol": "EURUSD"})
        assert result.capability is ConnectivityCapability.TRADING
        assert mt5.order_send.call_count == 0
        assert result.status in {
            ConnectivityStatus.OK,
            ConnectivityStatus.UNAVAILABLE,
        }


@pytest.mark.unit
class TestBrokerConnectivityService:
    def test_registry_and_invoke_unsupported(self) -> None:
        svc = BrokerConnectivityService.create(mt5=None)
        catalog = svc.catalog()
        assert any(c["platform"] == "bybit" for c in catalog)
        out = svc.invoke("bybit", "quotes", symbol="BTCUSDT")
        assert out["status"] == ConnectivityStatus.UNSUPPORTED.value

    def test_dashboard_shape(self) -> None:
        svc = BrokerConnectivityService.create(mt5=None)
        dash: dict[str, Any] = svc.dashboard()
        assert "catalog" in dash
        assert "matrix" in dash
        assert "diagnostics" in dash
        assert len(dash["matrix"]) >= 9
