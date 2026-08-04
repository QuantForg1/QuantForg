"""Unit tests — Signal Intelligence v2 (LIVE observation only)."""

from __future__ import annotations

from app.application.services import signal_intelligence_service as si
from app.application.services.institutional_multi_asset_scanner import _store_last_scan


def test_heatmap_and_probability_from_live_scan() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-04T20:00:00Z",
            "universe": ["XAUUSD", "EURUSD"],
            "rows": [
                {
                    "symbol": "XAUUSD",
                    "direction": "BUY",
                    "trade_quality": 92,
                    "ai_confidence": 84,
                    "reject": False,
                    "estimated_probability": 88.5,
                    "momentum": 70,
                    "structure": 80,
                },
                {
                    "symbol": "EURUSD",
                    "direction": "SELL",
                    "trade_quality": 81,
                    "ai_confidence": 79,
                    "reject": False,
                    "momentum": 60,
                    "structure": 65,
                },
            ],
        }
    )
    heat = si.build_heatmap()
    assert heat["fabricated"] is False
    assert heat["count"] == 2
    assert heat["cells"][0]["symbol"] in {"XAUUSD", "EURUSD"}
    probs = si.build_probabilities()
    assert probs["fabricated"] is False
    xau = next(i for i in probs["items"] if i["symbol"] == "XAUUSD")
    assert float(xau["probability"]) == 88.5


def test_observe_and_history_ops_fallback(monkeypatch) -> None:
    store: dict = {"items": []}

    def _load():
        return {"signal_history": store}

    def _save(payload):
        sh = payload.get("signal_history")
        if isinstance(sh, dict):
            store["items"] = list(sh.get("items") or [])
            store["updated_at"] = sh.get("updated_at")

    monkeypatch.setattr(si, "_upsert_history_postgres", lambda rows: 0)
    monkeypatch.setattr(si, "load_ops_state", _load)
    monkeypatch.setattr(si, "save_ops_state", _save)
    monkeypatch.setattr(si, "_load_history_postgres", lambda **kwargs: [])

    _store_last_scan(
        {
            "as_of": "2026-08-04T21:00:00Z",
            "rows": [
                {
                    "symbol": "BTCUSD",
                    "direction": "BUY",
                    "trade_quality": 90,
                    "ai_confidence": 80,
                    "reject": False,
                }
            ],
        }
    )
    obs = si.observe_live_scan()
    assert obs["observed"] == 1
    assert obs["fabricated"] is False
    hist = si.list_signal_history(observe=False)
    assert hist["count"] >= 1
    assert hist["items"][0]["symbol"] == "BTCUSD"


def test_pair_all_symbols_and_kpis() -> None:
    deals = [
        {
            "ticket": 1,
            "position_id": 10,
            "symbol": "XAUUSD",
            "side": "buy",
            "volume": 0.01,
            "price": 4000.0,
            "profit": 0.0,
            "commission": 0.0,
            "swap": 0.0,
            "deal_type": "deal_buy",
            "time": "2026-08-04T10:00:00+00:00",
        },
        {
            "ticket": 2,
            "position_id": 10,
            "symbol": "XAUUSD",
            "side": "sell",
            "volume": 0.01,
            "price": 4010.0,
            "profit": 10.0,
            "commission": 0.0,
            "swap": 0.0,
            "deal_type": "deal_sell",
            "time": "2026-08-04T10:30:00+00:00",
        },
        {
            "ticket": 3,
            "position_id": 11,
            "symbol": "EURUSD",
            "side": "buy",
            "volume": 0.01,
            "price": 1.1,
            "profit": 0.0,
            "commission": 0.0,
            "swap": 0.0,
            "deal_type": "in",
            "time": "2026-08-04T11:00:00+00:00",
        },
        {
            "ticket": 4,
            "position_id": 11,
            "symbol": "EURUSD",
            "side": "sell",
            "volume": 0.01,
            "price": 1.09,
            "profit": -5.0,
            "commission": 0.0,
            "swap": 0.0,
            "deal_type": "out",
            "time": "2026-08-04T11:20:00+00:00",
        },
    ]
    # Normalize deal_type for pairing helper ("in"/"out" substrings)
    closed = si.pair_all_symbol_closed_trades(deals)
    assert len(closed) >= 1
    kpis = si._kpis_from_closed(closed)
    assert kpis["fabricated"] is False
    assert kpis["closed_trades"] >= 1


def test_chart_markers_from_history(monkeypatch) -> None:
    monkeypatch.setattr(
        si,
        "list_signal_history",
        lambda **kwargs: {
            "items": [
                {
                    "symbol": "XAUUSD",
                    "observed_at": "2026-08-04T12:00:00Z",
                    "direction": "BUY",
                    "quality": 90,
                    "confidence": 80,
                    "probability": 85,
                    "badge": "BUY",
                }
            ]
        },
    )
    markers = si.chart_markers("XAUUSD")
    assert markers["fabricated"] is False
    assert markers["count"] == 1
    assert markers["markers"][0]["shape"] == "arrowUp"
