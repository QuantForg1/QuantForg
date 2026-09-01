"""Multi-market live execution — existing robot, global research universe.

Does not send orders. Does not create a second worker, OMS, or gateway.
Does not weaken Risk / min-lot / max-position / ticket truth.
"""

from __future__ import annotations

import pytest

from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_multi_asset_scanner import (
    expand_live_liquid_scan_universe,
    focus_broker_discovered_scan_universe,
    isolate_parallel_scan_results,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.research_execution_bridge import (
    research_scan_focus_symbols,
    signal_execution_status,
)
from app.domain.enums.order import OrderSide, OrderType
from app.domain.institutional_trading.live_trading_control import (
    HARD_CEILING_MAX_POSITIONS,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
)
from core.config.environments import production_settings, testing_settings

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_production_gold_only_env_cannot_lock_live_universe() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        execution_universe_mode="GOLD_ONLY",
        gold_only_mode=True,
        multi_symbol_enabled=False,
    )
    assert str(settings.execution_universe_mode).upper() == "BROKER_DISCOVERED"
    assert settings.gold_only_mode is False
    assert settings.multi_symbol_enabled is True


def test_non_production_gold_only_still_clamps() -> None:
    settings = testing_settings(
        execution_universe_mode="GOLD_ONLY",
        gold_only_mode=True,
        multi_symbol_enabled=True,
    )
    assert str(settings.execution_universe_mode).upper() == "GOLD_ONLY"
    assert settings.gold_only_mode is True


def test_seed_and_research_map_to_live_catalogue_spellings() -> None:
    live = ("EURUSD_i", "GBPUSD_i", "XAUUSD_i", "EURGBP_i", "CADJPY_i")
    mapped = focus_broker_discovered_scan_universe(
        live,
        seed=("EURUSD", "XAUUSD", "GBPUSD"),
        research_focus=("EURGBP", "NOTAREALPAIR"),
        cap=36,
    )
    upper = {s.upper() for s in mapped}
    assert "EURUSD_I" in upper
    assert "GBPUSD_I" in upper
    assert "XAUUSD_I" in upper
    assert "EURGBP_I" in upper
    assert "NOTAREALPAIR" not in upper
    assert "CADJPY_I" not in upper
    assert all(s in live for s in mapped)


def test_expand_adds_live_liquid_cross_absent_from_seed() -> None:
    live = (
        "EURUSD_i",
        "GBPUSD_i",
        "XAUUSD_i",
        "EURGBP_i",
        "CADJPY_i",
        "DISABLEDX",
    )
    focused = focus_broker_discovered_scan_universe(
        live,
        seed=("EURUSD", "XAUUSD", "GBPUSD"),
        research_focus=(),
        cap=36,
    )
    assert "CADJPY_i" not in focused
    rows = (
        {"code": "EURUSD_i", "trade_mode": 4, "digits": 5},
        {"code": "GBPUSD_i", "trade_mode": 4, "digits": 5},
        {"code": "XAUUSD_i", "trade_mode": 4, "digits": 3},
        {"code": "EURGBP_i", "trade_mode": 4, "digits": 5},
        {"code": "CADJPY_i", "trade_mode": 4, "digits": 3},
        {"code": "DISABLEDX", "trade_mode": 0, "digits": 5},
    )
    expanded = expand_live_liquid_scan_universe(
        live,
        focused=focused,
        broker_symbol_rows=rows,
        cap=36,
    )
    upper = {s.upper() for s in expanded}
    assert "EURUSD_I" in upper
    assert "GBPUSD_I" in upper
    assert "XAUUSD_I" in upper
    assert "CADJPY_I" in upper
    assert "EURGBP_I" in upper
    assert "DISABLEDX" not in upper
    assert len(expanded) <= 36


def test_unknown_research_symbol_is_not_invented() -> None:
    mapped = focus_broker_discovered_scan_universe(
        ("EURUSD_i",),
        seed=(),
        research_focus=("EURUSD", "FAKEUSD"),
    )
    assert mapped == ("EURUSD_i",)


def test_parse_order_intent_buy_and_sell_non_gold() -> None:
    buy = parse_order_intent(
        symbol="EURUSD",
        side="buy",
        order_type="market",
        volume="0.01",
    )
    sell = parse_order_intent(
        symbol="GBPUSD",
        side="sell",
        order_type="market",
        volume="0.01",
    )
    assert buy.symbol.upper() in {"EURUSD", "EURUSD_I"}
    assert buy.side is OrderSide.BUY
    assert buy.order_type is OrderType.MARKET
    assert sell.symbol.upper() in {"GBPUSD", "GBPUSD_I"}
    assert sell.side is OrderSide.SELL
    assert sell.order_type is OrderType.MARKET


def test_existing_oms_maps_limit_without_converting_to_market() -> None:
    buy_limit = parse_order_intent(
        symbol="EURUSD",
        side="buy",
        order_type="limit",
        volume="0.01",
        price="1.0800",
    )
    sell_limit = parse_order_intent(
        symbol="GBPUSD",
        side="sell",
        order_type="limit",
        volume="0.01",
        price="1.2500",
    )
    assert buy_limit.order_type is OrderType.LIMIT
    assert sell_limit.order_type is OrderType.LIMIT
    assert MT5OrderValidationService._action_for(buy_limit) == "buy_limit"
    assert MT5OrderValidationService._action_for(sell_limit) == "sell_limit"
    market = parse_order_intent(
        symbol="EURUSD",
        side="buy",
        order_type="market",
        volume="0.01",
    )
    assert MT5OrderValidationService._action_for(market) == "buy"


def test_one_symbol_failure_does_not_stop_other_opportunities() -> None:
    rows = isolate_parallel_scan_results(
        ("EURUSD_i", "GBPUSD_i", "XAUUSD_i"),
        (
            RuntimeError("gateway failure"),
            {
                "symbol": "GBPUSD_I",
                "reject": False,
                "direction": "SELL",
                "ai_confidence": 88,
                "trade_quality": 90,
            },
            {
                "symbol": "XAUUSD_I",
                "reject": True,
                "reject_reason": "RISK_REJECTED",
                "direction": "SELL",
            },
        ),
    )
    assert rows[0]["reject"] is True
    assert "EXECUTION_ERROR" in str(rows[0]["reject_reason"])
    assert rows[1]["reject"] is False
    assert rows[1]["direction"] == "SELL"
    assert rows[2]["reject_reason"] == "RISK_REJECTED"


def test_max_positions_ceiling_unchanged() -> None:
    assert HARD_CEILING_MAX_POSITIONS == 2


def test_min_lot_exceeds_risk_budget_code_unchanged() -> None:
    assert CODE_MIN_LOT_EXCEEDS_RISK_BUDGET == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_buy_and_sell_signals_are_both_live_eligible() -> None:
    buy = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD", "GBPUSD"],
    )
    sell = signal_execution_status(
        {"symbol": "GBPUSD", "direction": "SELL"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD", "GBPUSD"],
    )
    assert buy == "LIVE_ELIGIBLE"
    assert sell == "LIVE_ELIGIBLE"


def test_research_scan_focus_does_not_require_live_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.services.market_universe_service.get_last_market_universe_snapshot",
        lambda: {
            "opportunity_board": {
                "live_ranked": [
                    {
                        "symbol": "EURUSD",
                        "direction": "BUY",
                        "opportunity_score": 82,
                    },
                    {
                        "symbol": "GBPUSD",
                        "direction": "SELL",
                        "opportunity_score": 77,
                    },
                    {
                        "symbol": "USDJPY",
                        "direction": "WAIT",
                        "opportunity_score": 91,
                    },
                ]
            }
        },
    )
    focus = research_scan_focus_symbols()
    assert "EURUSD" in focus
    assert "GBPUSD" in focus
    assert "USDJPY" not in focus


def test_no_fill_without_ticket_on_non_gold() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "FILLED"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "EXECUTION_BLOCKED"
    submitted = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "FILLED", "ticket": 575672122},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert submitted == "ORDER_SUBMITTED"
