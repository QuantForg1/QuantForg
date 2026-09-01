"""Phase 74 — global research independent of user MT5; live trading stays gated."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.application.services import signal_center_service
from app.application.services.research_analysis_worker import (
    run_research_analysis_once,
)
from app.application.services.signal_center_service import (
    _row_from_research_opportunity,
)
from app.domain.market_universe.concurrency import map_isolated
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.scheduler import research_scan_order
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.presentation.routers import symbol_signals

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_signals_api_does_not_bind_user_mt5() -> None:
    src = Path(symbol_signals.__file__).read_text(encoding="utf-8")
    assert "ensure_live_mt5_session_for_user" not in src
    service_src = Path(signal_center_service.__file__).read_text(encoding="utf-8")
    assert '"broker_required_for_research": False' in service_src
    assert '"allow_live_promotion": False' in service_src


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_worker_runs_without_user_adapter() -> None:
    with patch(
        "app.application.services.market_universe_service.MarketUniverseService.snapshot",
        return_value={
            "catalogue_source": "UNAVAILABLE",
            "observability": {},
            "research_signals": {"n": 0},
        },
    ):
        health = run_research_analysis_once(mt5_adapter=None)
    assert health["authorizes_trade"] is False
    assert health["second_scanner"] is False
    assert health["forwarded_to_oms"] is False
    assert ALLOW_LIVE_PROMOTION is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_one_instrument_failure_does_not_stop_batch() -> None:
    def boom(item: str) -> str:
        if item == "BAD":
            raise RuntimeError("quote_failed")
        return item.upper()

    rows = map_isolated(["EURUSD", "BAD", "XAUUSD"], boom, max_workers=2)
    assert len(rows) == 3
    assert [r["ok"] for r in rows].count(True) == 2
    assert any(r["state"] == "ERROR" and r["item"] == "BAD" for r in rows)


@pytest.mark.unit
@pytest.mark.trading_core
def test_market_closed_is_skipped_not_fatal() -> None:
    closed = [
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "MARKET_CLOSED"},
        },
        {
            "canonical_symbol": "BTCUSD",
            "broker_symbol": "BTCUSD",
            "asset_class": "CRYPTO",
            "data_quality": {"state": "LIVE"},
        },
    ]
    schedule = research_scan_order(closed, max_batch=8)
    desks = {q["canonical_symbol"] for q in schedule["queue"]}
    assert "EURUSD" not in desks
    assert "BTCUSD" in desks
    assert schedule["skipped_n"] >= 1


@pytest.mark.unit
@pytest.mark.trading_core
def test_crypto_weekend_rotation_prefers_crypto() -> None:
    from app.domain.market_universe.scheduler import _WEEKEND_CLASS_ROTATION

    assert _WEEKEND_CLASS_ROTATION[0] == "CRYPTO"


@pytest.mark.unit
@pytest.mark.trading_core
def test_price_entry_sl_tp_survive_research_row_map() -> None:
    mapped = _row_from_research_opportunity(
        {
            "broker_symbol": "EURUSD",
            "symbol": "EURUSD",
            "direction": "BUY",
            "price": 1.0845,
            "bid": 1.0844,
            "ask": 1.0846,
            "entry": 1.085,
            "stop_loss": 1.08,
            "take_profit": 1.095,
            "RR": 2.0,
            "opportunity_score": 70,
            "directional_edge": 12,
            "evidence": {"REGIME": "TREND", "WHY_THIS_DIRECTION": "Impulse"},
            "reason": "Trend continuation",
        }
    )
    assert mapped["price"] == 1.0845
    assert mapped["entry"] == 1.085
    assert mapped["stop_loss"] == 1.08
    assert mapped["take_profit"] == 1.095
    assert mapped["bid"] == 1.0844
    assert mapped["ask"] == 1.0846
    assert mapped["pipeline"]["forwarded_to_oms"] is False
    assert mapped["pipeline"]["research_can_execute"] is False
    assert mapped["authorizes_trade"] is False
    assert mapped["evidence"]["WHY_THIS_DIRECTION"] == "Impulse"


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_cannot_submit_oms_order() -> None:
    with pytest.raises(ResearchExecutionBlocked):
        submit_order({"symbol": "EURUSD", "volume": 0.01})


@pytest.mark.unit
@pytest.mark.trading_core
def test_live_trading_enable_still_owner_admin_only() -> None:
    src = (
        ROOT / "app" / "presentation" / "routers" / "live_trading_control.py"
    ).read_text(encoding="utf-8")
    assert "require_roles(UserRole.OWNER, UserRole.ADMIN)" in src
    assert 'prefix="/live-trading"' in src


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_second_research_worker_or_robot_module() -> None:
    scanner = ROOT / "app" / "application" / "services" / "second_scanner.py"
    robot = ROOT / "app" / "application" / "services" / "second_robot.py"
    assert not scanner.exists()
    assert not robot.exists()
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert main.count('name="research-analysis-worker"') == 1


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_layout_not_in_trader_rail() -> None:
    nav = (
        ROOT / "frontend" / "src" / "components" / "layout" / "nav-config.ts"
    ).read_text(encoding="utf-8")
    desks = nav[
        nav.index("export const TRADER_DESK_ORDER") : nav.index(
            "export const OPERATOR_RAIL_ORDER"
        )
    ]
    assert '"/signals"' in desks
    assert '"/markets"' in desks
    assert '"/admin"' not in desks
    fn = nav[
        nav.index("export function visiblePrimaryRail") : nav.index(
            "export function visibleCommandItems"
        )
    ]
    assert "TRADER_DESK_ORDER" in fn
