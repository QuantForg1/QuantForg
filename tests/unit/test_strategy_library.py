"""Catalogue plugins added to the strategy engine. Intentions only."""

from __future__ import annotations

from app.application.services.strategy_engine import StrategyEngine
from app.domain.interfaces.strategy_engine import OhlcBar
from app.strategies.library import library_plugins


def _bars(n: int, *, start: float = 100.0, step: float = 0.0, volume: float = 0.0) -> list[OhlcBar]:
    price = start
    rows: list[OhlcBar] = []
    for i in range(n):
        price += step
        rows.append(
            OhlcBar(
                open=price - 0.02,
                high=price + 0.08,
                low=price - 0.08,
                close=price,
                volume=volume,
                time=f"2026-01-01T{i % 24:02d}:00:00+00:00",
            )
        )
    return rows


def test_library_is_registered_and_does_not_crash() -> None:
    engine = StrategyEngine()
    catalog = {item["key"] for item in engine.catalog()}
    for plugin in library_plugins():
        assert plugin.key in catalog
        result = engine.run(
            strategy_key=plugin.key,
            symbol="XAUUSD",
            timeframe="H1",
            bars=_bars(8),
        )
        assert result["ok"] is True
        assert result["signal"]["action"] in {"BUY", "SELL", "HOLD", "EXIT"}
        assert result["signal"]["explanations"]


def test_donchian_buys_a_rising_close() -> None:
    engine = StrategyEngine()
    result = engine.run(
        strategy_key="donchian_breakout",
        symbol="XAUUSD",
        timeframe="H1",
        bars=_bars(40, step=0.4),
        params={"period": 10},
    )
    assert result["signal"]["action"] == "BUY"


def test_vwap_holds_without_volume() -> None:
    engine = StrategyEngine()
    result = engine.run(
        strategy_key="vwap_reversion",
        symbol="XAUUSD",
        timeframe="H1",
        bars=_bars(30, volume=0.0),
    )
    assert result["signal"]["action"] == "HOLD"
    assert "volume" in result["signal"]["reasons"][0].lower()


def test_session_breakout_holds_without_timestamps() -> None:
    engine = StrategyEngine()
    bars = _bars(12)
    bars = [
        OhlcBar(open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume, time="")
        for b in bars
    ]
    result = engine.run(
        strategy_key="session_breakout",
        symbol="XAUUSD",
        timeframe="H1",
        bars=bars,
    )
    assert result["signal"]["action"] == "HOLD"
    assert "time" in result["signal"]["reasons"][0].lower()
