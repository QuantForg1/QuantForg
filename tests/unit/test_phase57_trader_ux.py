"""Phase 57 — market intelligence desk contracts; frozen trading path."""

from __future__ import annotations

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


@pytest.mark.unit
def test_research_remains_non_executable() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert RESEARCH_MAY_EXECUTE is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="SELL", volume="0.01")
    iso = scan_package_isolation()
    assert iso["isolated"] is True
    assert iso["ALLOW_LIVE_PROMOTION"] is False


@pytest.mark.unit
def test_buy_and_sell_remain_independent() -> None:
    buy = project_opportunity_row(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 80,
            "directional_edge": 8,
        }
    )
    sell = project_opportunity_row(
        {
            "symbol": "GBPUSD",
            "broker_symbol": "GBPUSD",
            "direction": "SELL",
            "opportunity_score": 82,
            "directional_edge": 9,
        }
    )
    assert buy["direction"] == "BUY"
    assert sell["direction"] == "SELL"
    assert buy["authorizes_trade"] is False
    assert sell["authorizes_trade"] is False


@pytest.mark.unit
def test_single_runtime_unchanged() -> None:
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    assert scan_package_isolation()["isolated"] is True
