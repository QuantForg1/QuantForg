"""Phase 59 — trader workspace UX pass; frozen trading path."""

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
_TOPBAR = _ROOT / "frontend" / "src" / "components" / "layout" / "topbar.tsx"
_SIGNALS = (
    _ROOT / "frontend" / "src" / "components" / "trading" / "signals-workspace.tsx"
)


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_single_runtime_and_no_execute_controls() -> None:
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    assert scan_package_isolation()["isolated"] is True
    signals = _SIGNALS.read_text(encoding="utf-8")
    assert "BUY ORDER" not in signals
    assert "SELL ORDER" not in signals
    assert "TRADE NOW" not in signals
    assert "submit_order" not in signals
    assert "RESEARCH_SIGNAL" in signals


@pytest.mark.unit
def test_trader_copy_hides_implementation_terms() -> None:
    ux = _TRADER_UX.read_text(encoding="utf-8")
    topbar = _TOPBAR.read_text(encoding="utf-8")
    assert 'return "BROKER NOT CONNECTED"' in ux
    assert 'return "LIVE"' in ux
    assert "Global Account" not in ux
    assert "Default Account" not in ux
    assert "Main Account" not in ux
    assert ">MT5<" not in topbar
    assert ">Gateway<" not in topbar


@pytest.mark.unit
def test_concurrent_live_sessions_remain_unsupported() -> None:
    text = (_ROOT / "app/application/services/trading_session.py").read_text(
        encoding="utf-8"
    )
    assert '"concurrent_live_sessions_supported": False' in text
