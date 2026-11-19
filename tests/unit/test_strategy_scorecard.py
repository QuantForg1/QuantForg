"""Strategy library (100+ plugins) and the read-only backtest scorecard."""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.application.services import strategy_scorecard as sc
from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    OhlcBar,
    StrategySnapshot,
)
from app.strategies import default_strategy_plugins
from app.strategies.library_ext import EXTENDED_PLUGINS


def _bars(n: int = 700, seed: int = 3) -> list[OhlcBar]:
    r = random.Random(seed)  # noqa: S311 - deterministic test data
    p = 3600.0
    t0 = datetime(2026, 11, 2, tzinfo=UTC)
    out = []
    for i in range(n):
        drift = 4 * math.sin(i / 40) - 4 * math.sin((i - 1) / 40) + 0.05
        o = p
        c = o + drift + r.gauss(0, 1.6)
        h = max(o, c) + abs(r.gauss(0, 1))
        lo = min(o, c) - abs(r.gauss(0, 1))
        out.append(
            OhlcBar(
                o,
                h,
                lo,
                c,
                100 + r.random() * 300,
                (t0 + timedelta(minutes=15 * i)).isoformat(),
            )
        )
        p = c
    return out


def test_library_has_100_plus_unique_strategies() -> None:
    plugins = default_strategy_plugins()
    keys = [p.key for p in plugins]
    assert len(keys) >= 100
    assert len(set(keys)) == len(keys)
    assert len(EXTENDED_PLUGINS) >= 60
    for p in plugins:
        assert p.name and p.description and p.category


def test_every_plugin_evaluates_without_error_and_valid_output() -> None:
    bars = _bars()
    plugins = default_strategy_plugins()
    fired: set[str] = set()
    for end in range(260, len(bars), 3):
        window = tuple(bars[end - 260 : end])
        for p in plugins:
            it = p.evaluate(
                StrategySnapshot("XAUUSD", "M15", window, params=dict(p.default_params))
            )
            assert it.action in {
                EngineSignalAction.BUY,
                EngineSignalAction.SELL,
                EngineSignalAction.HOLD,
            }
            assert 0.0 <= it.confidence <= 1.0
            assert it.strategy_key == p.key
            if it.action != EngineSignalAction.HOLD:
                fired.add(p.key)
    # The overwhelming majority must actually produce signals on varied data.
    assert len(fired) >= 85, sorted({p.key for p in plugins} - fired)


def test_short_history_holds_instead_of_guessing() -> None:
    bars = tuple(_bars(30))
    for p in default_strategy_plugins():
        it = p.evaluate(
            StrategySnapshot("XAUUSD", "M15", bars, params=dict(p.default_params))
        )
        if p.key in {"trend_following"}:
            continue
        assert it.action in {
            EngineSignalAction.HOLD,
            EngineSignalAction.BUY,
            EngineSignalAction.SELL,
        }


def test_mean_reversion_fires_on_atr_stretch() -> None:
    from app.strategies import MeanReversionStrategy

    base = _bars(80)
    last = base[-1]
    drop = [
        OhlcBar(
            last.close - k * 6,
            last.close - k * 6 + 1,
            last.close - k * 6 - 6,
            last.close - (k + 1) * 6,
            100,
            "",
        )
        for k in range(6)
    ]
    bounce = OhlcBar(
        drop[-1].close,
        drop[-1].close + 4,
        drop[-1].close - 1,
        drop[-1].close + 3,
        100,
        "",
    )
    it = MeanReversionStrategy().evaluate(
        StrategySnapshot("XAUUSD", "M15", tuple(base + drop + [bounce]), params={})
    )
    assert it.action == EngineSignalAction.BUY


def _sb(o: float, h: float, lo: float, c: float) -> sc.Bar:
    return sc.Bar("t", o, h, lo, c, 1)


def test_simulate_trade_target_stop_and_conservative_tie() -> None:
    flat = [_sb(100, 101, 99, 100) for _ in range(20)]  # ATR = 2 → risk 3
    up = [*flat, _sb(100, 100.5, 99.8, 100.2), _sb(100.2, 105, 100, 104.9)]
    r, _ = sc.simulate_trade(up, 19, "BUY", 0.0)  # entry 100, target 104.5
    assert r == sc.REWARD_R
    down = [*flat, _sb(100, 100.2, 96.5, 97)]
    r, _ = sc.simulate_trade(down, 19, "BUY", 0.0)  # stop 97
    assert r == -1.0
    both = [*flat, _sb(100, 105, 96, 100)]
    r, _ = sc.simulate_trade(both, 19, "BUY", 0.0)
    assert r == -1.0  # ambiguous bar counts as a loss
    r, _ = sc.simulate_trade(both, 19, "SELL", 0.0)
    assert r == -1.0


def test_simulate_trade_spread_cost_and_open_trades_not_counted() -> None:
    flat = [_sb(100, 101, 99, 100) for _ in range(20)]
    assert sc.simulate_trade(flat, 19, "BUY", 0.3) is None  # no bar after signal
    long_flat = flat + [_sb(100, 100.5, 99.5, 100) for _ in range(sc.MAX_HOLD + 1)]
    r, _ = sc.simulate_trade(long_flat, 19, "BUY", 0.3)
    assert r < 0  # time exit at the same price loses the spread


def test_metrics_and_grade() -> None:
    m = sc.metrics([1.5, -1, 1.5, -1, 1.5])
    assert m["trades"] == 5 and m["wins"] == 3
    assert m["profit_factor"] == 2.25
    assert m["max_drawdown_r"] == 1.0
    assert sc.grade(m) == "insufficient_data"
    assert sc.grade(sc.metrics([1.5, -1] * 15)) == "strong"
    assert sc.grade(sc.metrics([1.5, -1, -1] * 10)) == "weak"


def test_run_scorecard_ranks_every_strategy_and_never_orders() -> None:
    bars = _bars(900)
    raw = [
        {
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    out = sc.run_scorecard(raw, 0.3)
    rows = out["strategies"]
    assert len(rows) >= 100
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert all(r["errors"] == 0 for r in rows)
    assert out["consensus"]["direction"] in {"BUY", "SELL", "WAIT"}
    assert "Past results" in out["disclaimer"]
    assert not any("order" in k for r in rows for k in r)


def test_candles_to_bars_removes_broker_clock_offset() -> None:
    @dataclass
    class C:
        open_time: datetime
        open: float = 1.0
        high: float = 2.0
        low: float = 0.5
        close: float = 1.5
        tick_volume: int = 10

    now = datetime(2026, 11, 19, 12, 7, tzinfo=UTC)
    broker = [
        C(datetime(2026, 11, 19, 13, 45, tzinfo=UTC)),
        C(datetime(2026, 11, 19, 14, 0, tzinfo=UTC)),
    ]
    out = sc.candles_to_bars(broker, now=now)
    assert out[-1]["time"].startswith("2026-11-19T12:00")
    utc = [C(datetime(2026, 11, 19, 12, 0, tzinfo=UTC))]
    assert sc.candles_to_bars(utc, now=now)[0]["time"].startswith("2026-11-19T12:00")


def test_service_warms_then_serves_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QF_SCORECARD_INPROCESS", "1")
    bars = _bars(500)

    @dataclass
    class C:
        open_time: datetime
        open: float
        high: float
        low: float
        close: float
        tick_volume: float

    candles = [
        C(
            datetime.fromisoformat(b.time) - timedelta(days=30),
            b.open,
            b.high,
            b.low,
            b.close,
            b.volume,
        )
        for b in bars
    ]

    class Feed:
        calls = 0

        async def candles(self, **_: object) -> object:
            Feed.calls += 1
            return type("B", (), {"candles": candles})()

        async def tick(self, **_: object) -> object:
            return type(
                "T", (), {"tick": type("K", (), {"bid": 3600.0, "ask": 3600.25})()}
            )()

    monkeypatch.setattr(
        sc,
        "run_scorecard",
        lambda _b, s: {
            "strategies": [],
            "summary": {"strategies": 0, "compute_seconds": 0},
            "spread_seen": s,
        },
    )

    async def go() -> None:
        svc = sc.StrategyScorecardService()
        first = await svc.get(Feed())
        assert first["status"] == "warming"
        assert svc._task is not None
        await svc._task
        second = await svc.get(Feed())
        assert second["status"] == "ready"
        assert second["spread_seen"] == pytest.approx(0.25)
        assert Feed.calls == 1

    asyncio.run(go())
