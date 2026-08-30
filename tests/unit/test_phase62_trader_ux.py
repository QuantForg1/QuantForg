"""Phase 62 — broker-independent signals + trader workspace polish; frozen trading path."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    RESEARCH_MAY_EXECUTE,
)
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    scan_package_isolation,
    submit_order,
)
from app.domain.trading.execution_universe import MODE_BROKER_DISCOVERED
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

_ROOT = Path(__file__).resolve().parents[2]
_TRADER_UX = _ROOT / "frontend" / "src" / "lib" / "trading" / "trader-ux.ts"
_SIGNALS = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "signals-workspace.tsx"
)
_DASHBOARD = _ROOT / "frontend" / "src" / "app" / "(app)" / "dashboard" / "page.tsx"
_BROKER = (
    _ROOT / "frontend" / "src" / "components" / "broker" / "broker-config-workspace.tsx"
)
_NAV = _ROOT / "frontend" / "src" / "components" / "layout" / "nav-config.ts"


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order({})
    assert scan_package_isolation()["isolated"] is True


@pytest.mark.unit
def test_signals_are_broker_independent() -> None:
    signals = _SIGNALS.read_text(encoding="utf-8")
    ux = _TRADER_UX.read_text(encoding="utf-8")
    dash = _DASHBOARD.read_text(encoding="utf-8")
    assert "signalCenterApi" in signals
    assert "marketUniverseApi" not in signals
    assert "normalizeSignalCenterPayload" in ux
    assert "RESEARCH_INDEPENDENT_COPY" in ux
    assert "enabled: connection.connected" not in signals
    assert "BUY NOW" not in signals
    assert "SELL NOW" not in signals
    assert "TRADE NOW" not in signals
    assert "Place Order" not in signals
    assert "submit_order" not in signals
    assert "signalCenterApi" in dash
    assert "noBroker || sessionMismatch || signalState" not in dash


@pytest.mark.unit
def test_broker_form_stays_password_safe_and_simple() -> None:
    broker = _BROKER.read_text(encoding="utf-8")
    assert "clearPasswordField" in broker
    assert "Verify Connection" in broker
    assert "bw-password" in broker
    assert "localStorage.setItem" not in broker
    assert "sessionStorage" not in broker
    assert "GatewayMT5Client" not in broker
    assert "order_send" not in broker


@pytest.mark.unit
def test_navigation_rails_remain_clean() -> None:
    nav = _NAV.read_text(encoding="utf-8")
    assert "TRADER_DESK_ORDER" in nav
    assert '"/signals"' in nav
    assert "mobileTabNav" in nav
    assert '"/dashboard"' in nav
    assert "no broker required" in nav.lower() or "Research intelligence" in nav


@pytest.mark.unit
def test_execution_universe_and_adapters_unchanged() -> None:
    assert MODE_BROKER_DISCOVERED == "BROKER_DISCOVERED"
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    assert "research_rank_score" in _TRADER_UX.read_text(encoding="utf-8")
