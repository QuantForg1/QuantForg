"""Phase 55 — trader Signals/Portfolio contracts without changing live trading."""

from __future__ import annotations

import ast
from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[2]
MT5_DIR = ROOT / "app" / "infrastructure" / "brokers" / "mt5"


@pytest.mark.unit
def test_live_promotion_and_research_execution_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")
    iso = scan_package_isolation()
    assert iso["isolated"] is True
    assert iso["ALLOW_LIVE_PROMOTION"] is False


@pytest.mark.unit
def test_opportunity_row_never_authorizes_trade() -> None:
    row = project_opportunity_row(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "direction": "BUY",
            "opportunity_score": 80,
            "directional_edge": 8,
        }
    )
    assert row["authorizes_trade"] is False
    assert row["live_execution_eligible"] is False
    assert row["ALLOW_LIVE_PROMOTION"] is False
    assert "NOT A TRADE AUTHORIZATION" in str(row["research_status_label"])


@pytest.mark.unit
def test_single_gateway_adapter_and_no_second_engine_modules() -> None:
    assert GatewayMT5Client.__name__ == "GatewayMT5Client"
    assert MT5Adapter.__name__ == "MT5Adapter"
    gateway_files = list(MT5_DIR.glob("*gateway*"))
    assert any(path.name == "gateway_client.py" for path in gateway_files)
    assert not (MT5_DIR / "gateway_client_v2.py").exists()
    assert not (ROOT / "app" / "domain" / "trading_engine_v2.py").exists()
    scanner = ROOT / "app" / "domain" / "market_universe" / "second_scanner.py"
    assert not scanner.exists()


@pytest.mark.unit
def test_portfolio_router_is_owner_scoped() -> None:
    text = (ROOT / "app" / "presentation" / "routers" / "portfolio.py").read_text(
        encoding="utf-8"
    )
    names: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Name):
            names.add(node.id)
    assert "CurrentUser" in names
    assert "user_id=user.id" in text
    assert "default_account" not in text.lower()
    assert "global portfolio" not in text.lower()
