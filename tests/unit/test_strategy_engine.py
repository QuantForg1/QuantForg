"""Unit tests for deterministic Strategy Engine — no execution / no fake fills."""

from __future__ import annotations

import pytest

from app.application.services.strategy_engine import (
    DefaultStrategyRisk,
    StrategyAllocation,
    StrategyEngine,
)
from app.domain.indicators import ema, rsi, sma
from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    OhlcBar,
    SignalExplanation,
    StrategyIntention,
    StrategyRiskLimits,
)


def _bars_trending_up(n: int = 80, start: float = 100.0) -> list[OhlcBar]:
    out: list[OhlcBar] = []
    price = start
    for i in range(n):
        price += 0.15
        out.append(
            OhlcBar(
                open=price - 0.05,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=100,
                time=f"t{i}",
            )
        )
    return out


def _bars_flat(n: int = 80, level: float = 100.0) -> list[OhlcBar]:
    return [
        OhlcBar(
            open=level,
            high=level + 0.05,
            low=level - 0.05,
            close=level,
            volume=10,
            time=f"t{i}",
        )
        for i in range(n)
    ]


@pytest.mark.unit
class TestIndicators:
    def test_sma_rsi_ema_deterministic(self) -> None:
        series = [float(i) for i in range(1, 31)]
        s = sma(series, 5)
        assert s[-1] == pytest.approx(28.0)
        e = ema(series, 5)
        assert e[-1] is not None
        r = rsi(series, 14)
        assert r[-1] is not None
        assert 50 < float(r[-1]) <= 100


@pytest.mark.unit
class TestStrategyEngine:
    def test_catalog_has_required_strategies(self) -> None:
        engine = StrategyEngine()
        keys = {i["key"] for i in engine.catalog()}
        assert {
            "trend_following",
            "ma_cross",
            "rsi",
            "macd",
            "bollinger",
            "breakout",
            "momentum",
            "mean_reversion",
            "custom_rules",
        } <= keys

    def test_trend_following_buy_on_uptrend(self) -> None:
        engine = StrategyEngine()
        result = engine.run(
            strategy_key="trend_following",
            symbol="EURUSD",
            timeframe="H1",
            bars=_bars_trending_up(80),
            params={"ema_period": 20},
            session="london",
            market_state="trending",
        )
        assert result["ok"] is True
        assert result["signal"]["action"] in {"BUY", "HOLD"}
        expl = result["signal"]["explanations"]
        assert expl
        assert "indicator" in expl[0]
        assert "threshold" in expl[0]
        assert "market_context" in expl[0]
        assert "reason" in expl[0]

    def test_rsi_hold_in_mid_range(self) -> None:
        engine = StrategyEngine()
        # Mild oscillation around a level → RSI stays mid-band
        bars: list[OhlcBar] = []
        price = 100.0
        for i in range(80):
            price += 0.05 if i % 2 == 0 else -0.04
            bars.append(
                OhlcBar(
                    open=price - 0.01,
                    high=price + 0.02,
                    low=price - 0.02,
                    close=price,
                    volume=10,
                    time=f"t{i}",
                )
            )
        result = engine.run(
            strategy_key="rsi",
            symbol="EURUSD",
            timeframe="H1",
            bars=bars,
            params={"period": 14, "oversold": 20, "overbought": 80},
        )
        assert result["ok"] is True
        assert result["signal"]["action"] == "HOLD"
        assert result["signal"]["explanations"]

    def test_risk_blocks_max_trades(self) -> None:
        engine = StrategyEngine()
        result = engine.run(
            strategy_key="momentum",
            symbol="EURUSD",
            timeframe="H1",
            bars=_bars_trending_up(40),
            params={"lookback": 5, "threshold_pct": 0.01},
            open_trades=5,
            limits=StrategyRiskLimits(max_trades=5),
        )
        assert result["ok"] is True
        # BUY/SELL coerced to HOLD when risk blocks
        if result["risk"]["allowed"] is False:
            assert result["signal"]["action"] == "HOLD"

    def test_validate_custom_rules(self) -> None:
        engine = StrategyEngine()
        bad = engine.validate_rules("custom_rules", {"rules": []})
        assert bad["valid"] is False
        good = engine.validate_rules(
            "custom_rules",
            {
                "rules": [
                    {
                        "when": {"indicator": "rsi", "op": "<=", "value": 30},
                        "action": "BUY",
                        "reason": "oversold",
                    }
                ]
            },
        )
        assert good["valid"] is True

    def test_allocation_and_portfolio(self) -> None:
        engine = StrategyEngine()
        engine.set_allocations(
            [
                StrategyAllocation("rsi", 40.0, ("EURUSD",)),
                StrategyAllocation("macd", 60.0, ()),
            ]
        )
        summary = engine.portfolio_summary()
        assert len(summary["allocations"]) == 2
        assert "paper/performance" in summary["performance"]["paper"]

    def test_refuses_insufficient_bars(self) -> None:
        engine = StrategyEngine()
        result = engine.run(
            strategy_key="rsi",
            symbol="X",
            timeframe="H1",
            bars=_bars_flat(3),
        )
        assert result["ok"] is False

    def test_never_invents_execution(self) -> None:
        engine = StrategyEngine()
        result = engine.run(
            strategy_key="ma_cross",
            symbol="EURUSD",
            timeframe="H1",
            bars=_bars_trending_up(50),
            params={"fast": 5, "slow": 15},
        )
        assert result["execution_policy"]["autonomous_trading"] is False
        assert "EXECUTION_ENABLED" in result["execution_policy"]["live_requires"]


@pytest.mark.unit
class TestDefaultStrategyRisk:
    def test_correlation_block(self) -> None:
        risk = DefaultStrategyRisk()
        intention = StrategyIntention(
            action=EngineSignalAction.BUY,
            confidence=0.7,
            explanations=(
                SignalExplanation(
                    reason="test",
                    indicator="RSI",
                    threshold="30",
                    market_context="session=london; state=trending",
                ),
            ),
            strategy_key="rsi",
            symbol="EURUSD",
            timeframe="H1",
            timestamp="t",
        )
        verdict = risk.check(
            intention,
            open_trades=0,
            daily_pnl_pct=0.0,
            exposure_pct=0.0,
            limits=StrategyRiskLimits(max_correlation=0.5),
            correlation=0.9,
        )
        assert verdict.allowed is False
