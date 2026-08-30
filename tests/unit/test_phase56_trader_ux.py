"""Phase 56 — Signals/Portfolio trader UX contracts, frozen trading path."""

from __future__ import annotations

import pytest

from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.opportunity_board import project_opportunity_row
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    scan_package_isolation,
    submit_order,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client


@pytest.mark.unit
def test_live_promotion_and_research_execution_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")
    iso = scan_package_isolation()
    assert iso["isolated"] is True
    assert iso["ALLOW_LIVE_PROMOTION"] is False


@pytest.mark.unit
def test_buy_and_sell_project_independently() -> None:
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
    assert buy["ALLOW_LIVE_PROMOTION"] is False
    assert sell["ALLOW_LIVE_PROMOTION"] is False


@pytest.mark.unit
def test_single_gateway_and_adapter_remain() -> None:
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
