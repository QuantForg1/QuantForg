"""Phase 58 — trader workspace contracts; frozen trading path."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    RESEARCH_MAY_EXECUTE,
)
from app.domain.market_universe.opportunity_board import project_opportunity_row
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    scan_package_isolation,
    submit_order,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_research_and_live_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_buy_sell_and_single_runtime() -> None:
    buy = project_opportunity_row(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 80,
        }
    )
    sell = project_opportunity_row(
        {
            "symbol": "GBPUSD",
            "broker_symbol": "GBPUSD",
            "direction": "SELL",
            "opportunity_score": 82,
        }
    )
    assert buy["direction"] == "BUY"
    assert sell["direction"] == "SELL"
    assert buy["authorizes_trade"] is False
    assert sell["authorizes_trade"] is False
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    assert scan_package_isolation()["isolated"] is True


@pytest.mark.unit
def test_concurrent_live_sessions_remain_unsupported() -> None:
    text = (_ROOT / "app/application/services/trading_session.py").read_text(
        encoding="utf-8"
    )
    assert '"concurrent_live_sessions_supported": False' in text
