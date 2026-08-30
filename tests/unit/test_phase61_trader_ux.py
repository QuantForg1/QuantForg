"""Phase 61 — broker universe + complete markets experience; frozen trading path."""

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
_MARKETS = _ROOT / "frontend" / "src" / "app" / "(app)" / "markets" / "page.tsx"
_SIGNALS = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "signals-workspace.tsx"
)
_DASHBOARD = _ROOT / "frontend" / "src" / "app" / "(app)" / "dashboard" / "page.tsx"
_CATALOGUE = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "market-catalogue-rows.tsx"
)
_BROKER = (
    _ROOT / "frontend" / "src" / "components" / "broker" / "broker-config-workspace.tsx"
)


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_execution_universe_remains_broker_discovered() -> None:
    assert MODE_BROKER_DISCOVERED == "BROKER_DISCOVERED"
    universe = (
        _ROOT / "app" / "domain" / "trading" / "execution_universe.py"
    ).read_text(encoding="utf-8")
    gold = (_ROOT / "frontend" / "src" / "lib" / "trading" / "gold-only.ts").read_text(
        encoding="utf-8"
    )
    ux = _TRADER_UX.read_text(encoding="utf-8")
    markets = _MARKETS.read_text(encoding="utf-8")
    assert "MODE_BROKER_DISCOVERED" in universe
    assert "MULTI_SYMBOL_ENABLED = true" in gold
    assert "DEFAULT_SCALPING_UNIVERSE" not in markets
    assert "GOLD_ONLY_FALLBACK" not in markets
    assert "hasResearchSignal" in ux
    assert "NO SIGNAL" in ux
    assert "cataloguePageSlice" in ux


@pytest.mark.unit
def test_markets_shows_full_broker_universe_contract() -> None:
    markets = _MARKETS.read_text(encoding="utf-8")
    catalogue = _CATALOGUE.read_text(encoding="utf-8")
    assert "BROKER-DISCOVERED MARKET UNIVERSE" in markets
    assert "marketUniverseApi.refresh" in markets
    assert "knownInstrumentCountLabel" in markets
    assert "Top 10" not in catalogue
    assert "Top 20" not in catalogue
    assert "MARKET_PAGE_SIZE" in catalogue
    assert "NO SIGNAL" in _TRADER_UX.read_text(encoding="utf-8")
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"


@pytest.mark.unit
def test_signals_remain_research_only_and_consistent() -> None:
    signals = _SIGNALS.read_text(encoding="utf-8")
    dash = _DASHBOARD.read_text(encoding="utf-8")
    broker = _BROKER.read_text(encoding="utf-8")
    assert "BUY ORDER" not in signals
    assert "SELL ORDER" not in signals
    assert "TRADE NOW" not in signals
    assert "Place Order" not in signals
    assert "submit_order" not in signals
    assert "hasResearchSignal" in signals
    assert "View all markets" in signals
    assert "View all markets" in dash
    assert "clearPasswordField" in broker
    assert "localStorage.setItem" not in broker
    assert "sessionStorage" not in broker
    assert scan_package_isolation()["isolated"] is True


@pytest.mark.unit
def test_concurrent_live_sessions_remain_unsupported() -> None:
    text = (_ROOT / "app/application/services/trading_session.py").read_text(
        encoding="utf-8"
    )
    assert '"concurrent_live_sessions_supported": False' in text
