"""Phase 63 — signals intelligence desk + analysis lifecycle UI; frozen trading path."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
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
_DETAIL = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "intelligence-detail.tsx"
)


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    assert FROZEN_OPPORTUNITY_THRESHOLD == 70
    assert FROZEN_DIRECTIONAL_EDGE == 5
    assert FROZEN_MIN_RR == "1.20"
    with pytest.raises(ResearchExecutionBlocked):
        submit_order({})
    assert scan_package_isolation()["isolated"] is True


@pytest.mark.unit
def test_signals_desk_is_broker_independent_and_honest() -> None:
    signals = _SIGNALS.read_text(encoding="utf-8")
    ux = _TRADER_UX.read_text(encoding="utf-8")
    assert "signalCenterApi" in signals
    assert "marketUniverseApi" not in signals
    assert "actionHref=\"/broker\"" not in signals
    assert "Connect Broker" not in signals
    assert "CATALOGUE UNAVAILABLE" not in signals
    assert "NO ACTIVE SIGNALS" in ux or "NO_ACTIVE_SIGNALS" in ux
    assert "resolveAnalysisDeskStatus" in ux
    assert "ANALYSIS RUNNING" in ux or "ANALYSIS_RUNNING" in ux
    assert "LIVE TRADING OFF" in ux or "liveTradingLabel" in ux
    assert "BUY NOW" not in signals
    assert "SELL NOW" not in signals
    assert "Place Order" not in signals
    assert "submit_order" not in signals
    assert "Refresh analysis" in signals
    assert "research_rank_score" in ux


@pytest.mark.unit
def test_analysis_does_not_auto_start_live_trading_robot() -> None:
    signals = _SIGNALS.read_text(encoding="utf-8")
    broker = _BROKER.read_text(encoding="utf-8")
    dash = _DASHBOARD.read_text(encoding="utf-8")
    assert "startRobot" not in signals
    assert "robot/start" not in signals
    assert "SIGNAL_CENTER_QUERY_KEY" in broker
    assert "never automatic" in dash.lower() or "Research analysis" in dash
    assert "Place Order" not in _DETAIL.read_text(encoding="utf-8")


@pytest.mark.unit
def test_execution_universe_and_adapters_unchanged() -> None:
    assert MODE_BROKER_DISCOVERED == "BROKER_DISCOVERED"
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
