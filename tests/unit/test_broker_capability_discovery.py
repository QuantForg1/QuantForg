"""Unit tests for broker capability discovery."""

from __future__ import annotations

import pytest

from app.domain.enums.broker import BrokerCapabilityCode
from app.domain.interfaces.broker_capability_discovery import (
    default_capabilities_for_platform,
    discover_adapter_capabilities,
)
from app.infrastructure.brokers.mt5 import MT5Adapter
from app.infrastructure.brokers.placeholders import PlaceholderBrokerAdapter


@pytest.mark.unit
class TestCapabilityDiscovery:
    def test_default_capabilities_include_market_data_and_history(self) -> None:
        caps = default_capabilities_for_platform("mt5")
        assert BrokerCapabilityCode.MARKET_DATA in caps
        assert BrokerCapabilityCode.HISTORY in caps
        assert BrokerCapabilityCode.ORDERS in caps
        assert BrokerCapabilityCode.POSITIONS in caps
        assert BrokerCapabilityCode.ACCOUNT_INFO in caps
        assert BrokerCapabilityCode.SYMBOLS in caps

    def test_placeholder_adapter_reports_platform_capabilities(self) -> None:
        adapter = MT5Adapter()
        discovered = adapter.discover_capabilities()
        assert BrokerCapabilityCode.MARKET_DATA in discovered
        assert BrokerCapabilityCode.CONNECT in discovered
        assert BrokerCapabilityCode.SYMBOLS in discovered
        # Portfolio engine: read-only positions/orders are advertised.
        assert BrokerCapabilityCode.ORDERS in discovered
        assert BrokerCapabilityCode.POSITIONS in discovered

    def test_discover_adapter_capabilities_fallback(self) -> None:
        class Bare:
            platform_code = "other"

        caps = discover_adapter_capabilities(Bare())
        assert BrokerCapabilityCode.CONNECT in caps
        assert BrokerCapabilityCode.ACCOUNT_INFO in caps

    def test_discover_uses_discovery_port_when_present(self) -> None:
        adapter = PlaceholderBrokerAdapter()
        adapter.platform_code = "ctrader"
        caps = discover_adapter_capabilities(adapter)
        assert BrokerCapabilityCode.MARKET_DATA in caps
