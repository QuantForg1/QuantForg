"""Phase 60 — trader workspace command center; frozen trading path."""

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
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

_ROOT = Path(__file__).resolve().parents[2]
_TRADER_UX = _ROOT / "frontend" / "src" / "lib" / "trading" / "trader-ux.ts"
_SIGNALS = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "signals-workspace.tsx"
)
_DASHBOARD = _ROOT / "frontend" / "src" / "app" / "(app)" / "dashboard" / "page.tsx"


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_signals_remain_research_only() -> None:
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    assert scan_package_isolation()["isolated"] is True
    signals = _SIGNALS.read_text(encoding="utf-8")
    assert "BUY ORDER" not in signals
    assert "SELL ORDER" not in signals
    assert "TRADE NOW" not in signals
    assert "Place Order" not in signals
    assert "submit_order" not in signals
    assert "research_rank_score" in _TRADER_UX.read_text(encoding="utf-8")
    assert "Search symbol" in signals
    assert "Strongest edge" in signals


@pytest.mark.unit
def test_dashboard_command_links_and_no_global_account() -> None:
    dash = _DASHBOARD.read_text(encoding="utf-8")
    ux = _TRADER_UX.read_text(encoding="utf-8")
    assert "View all signals" in dash
    assert "View portfolio" in dash
    assert "View all markets" in dash
    assert "Open terminal" in dash
    assert "Global Account" not in dash
    assert "Default Account" not in ux
    assert "Main Account" not in ux


@pytest.mark.unit
def test_concurrent_live_sessions_remain_unsupported() -> None:
    text = (_ROOT / "app/application/services/trading_session.py").read_text(
        encoding="utf-8"
    )
    assert '"concurrent_live_sessions_supported": False' in text
