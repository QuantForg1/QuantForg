"""Unit tests — Symbol Management + Signal Center (UI/API services)."""

from __future__ import annotations

from app.application.services import signal_center_service, symbol_management_service
from app.application.services.institutional_multi_asset_scanner import _store_last_scan
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)


def test_symbol_update_and_enabled_order(monkeypatch) -> None:
    store: dict[str, dict] = {}

    monkeypatch.setattr(
        symbol_management_service,
        "load_preferences",
        lambda force=False: {k: dict(v) for k, v in store.items()},
    )

    def _persist(prefs):
        store.clear()
        store.update({k: dict(v) for k, v in prefs.items()})

    monkeypatch.setattr(symbol_management_service, "_persist", _persist)
    monkeypatch.setattr(
        symbol_management_service,
        "sync_allowed_symbols_to_plane",
        lambda **kwargs: symbol_management_service.enabled_symbols_ordered(store),
    )
    monkeypatch.setattr(
        symbol_management_service,
        "_broker_catalogue_rows",
        lambda: [
            {"name": "XAUUSD", "trade_mode": 4, "description": "Gold"},
            {"name": "EURUSD", "trade_mode": 4, "description": "Euro"},
            {"name": "AUDJPY", "trade_mode": 4, "description": "Aussie Yen"},
        ],
    )

    symbol_management_service.update_symbol(
        "XAUUSD", enabled=True, priority=1, sync_plane=True
    )
    symbol_management_service.update_symbol(
        "EURUSD", enabled=True, priority=2, sync_plane=True
    )
    symbol_management_service.update_symbol(
        "AUDJPY", enabled=False, priority=3, sync_plane=True
    )

    ordered = symbol_management_service.enabled_symbols_ordered(store)
    assert ordered == ["XAUUSD", "EURUSD"]

    listing = symbol_management_service.list_managed_symbols()
    assert listing["total"] >= 3
    by_sym = {i["symbol"]: i for i in listing["items"]}
    assert by_sym["AUDJPY"]["enabled"] is False
    assert by_sym["XAUUSD"]["priority"] == 1


def test_bulk_and_reorder(monkeypatch) -> None:
    store: dict[str, dict] = {}
    monkeypatch.setattr(
        symbol_management_service,
        "load_preferences",
        lambda force=False: {k: dict(v) for k, v in store.items()},
    )

    def _persist(prefs):
        store.clear()
        store.update({k: dict(v) for k, v in prefs.items()})

    monkeypatch.setattr(symbol_management_service, "_persist", _persist)
    monkeypatch.setattr(
        symbol_management_service,
        "sync_allowed_symbols_to_plane",
        lambda **kwargs: symbol_management_service.enabled_symbols_ordered(store),
    )

    symbol_management_service.bulk_update(
        symbols=["BTCUSD", "ETHUSD", "GBPUSD"], enable=True
    )
    result = symbol_management_service.reorder_priorities(
        ["GBPUSD", "BTCUSD", "ETHUSD"]
    )
    assert result["enabled_symbols"][0] == "GBPUSD"
    assert store["GBPUSD"]["priority"] == 1


def test_signal_center_uses_live_scan_not_fabricated() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-04T12:00:00Z",
            "universe": ["XAUUSD", "EURUSD"],
            "rows": [
                {
                    "symbol": "XAUUSD",
                    "direction": "BUY",
                    "trade_quality": 94,
                    "ai_confidence": 82,
                    "reject": False,
                    "momentum": 70,
                    "structure": 80,
                },
                {
                    "symbol": "EURUSD",
                    "direction": "NONE",
                    "trade_quality": 40,
                    "ai_confidence": 30,
                    "reject": True,
                    "reject_reason": "Weak structure",
                },
            ],
        }
    )
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["fabricated"] is False
    assert payload["source"] == "live_multi_asset_scan"
    assert payload["dashboard"]["buy_signals"] >= 1
    symbols = {i["symbol"] for i in payload["items"]}
    assert "XAUUSD" in symbols
    xau = next(i for i in payload["items"] if i["symbol"] == "XAUUSD")
    assert xau["badge"] in {"BUY", "STRONG BUY", "WEAK BUY"}
    assert xau["quality"] == 94


def test_scalping_enforces_operator_multi_symbol_allowlist() -> None:
    from decimal import Decimal

    policy = AutoTradePolicy(
        enabled=True,
        run_state="running",
        trading_mode="scalping",
        allowed_symbols=("XAUUSD", "EURUSD", "GBPUSD"),
    )
    facts = AutoTradeLiveFacts(
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        risk_engine_pass=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol="AUDJPY",
        symbol_tradable=True,
        margin_available=True,
        no_broker_restrictions=True,
        open_positions=0,
        session="london",
        spread=Decimal("0.40"),
        news_blocked=False,
        daily_loss_exceeded=False,
        emergency_stop=False,
        ops_mode="LIVE",
        execution_enabled=True,
    )
    blocked = evaluate_auto_trade_safety(policy, facts)
    assert blocked.allowed is False
    assert any("not in allowed list" in r for r in blocked.failed_reasons)

    ok = evaluate_auto_trade_safety(
        policy,
        AutoTradeLiveFacts(
            gateway_connected=True,
            broker_connected=True,
            market_data_live=True,
            risk_engine_pass=True,
            account_trading_enabled=True,
            mt5_autotrading_enabled=True,
            symbol="EURUSD",
            symbol_tradable=True,
            margin_available=True,
            no_broker_restrictions=True,
            open_positions=0,
            session="london",
            spread=Decimal("0.40"),
            news_blocked=False,
            daily_loss_exceeded=False,
            emergency_stop=False,
            ops_mode="LIVE",
            execution_enabled=True,
        ),
    )
    assert ok.allowed is True
