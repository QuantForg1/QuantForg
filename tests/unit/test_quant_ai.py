"""Unit tests for Quant AI domain — real-input analysis, never invents quotes."""

from __future__ import annotations

from app.domain.quant_ai.correlation import correlation_from_closes
from app.domain.quant_ai.execution_ai import analyze_execution_ai
from app.domain.quant_ai.market_structure import analyze_symbol_structure
from app.domain.quant_ai.portfolio_ai import analyze_portfolio_ai, review_trade
from app.domain.quant_ai.risk_ai import analyze_risk_ai


def _uptrend_candles(n: int = 80, start: float = 1.08) -> list[dict]:
    out = []
    price = start
    for _i in range(n):
        o = price
        c = price + 0.0004
        h = c + 0.0001
        low = o - 0.00005
        out.append({"open": o, "high": h, "low": low, "close": c})
        price = c
    return out


def test_market_structure_insufficient_bars() -> None:
    result = analyze_symbol_structure(symbol="EURUSD", candles=_uptrend_candles(10))
    assert result["status"] == "unavailable"
    assert result["autonomous_trading"] is False


def test_market_structure_bullish_with_why() -> None:
    result = analyze_symbol_structure(
        symbol="EURUSD",
        candles=_uptrend_candles(220),
        bid=1.10,
        ask=1.1001,
        session="London",
    )
    assert result["status"] == "available"
    assert result["trend"] == "Bullish"
    assert result["confidence_pct"] > 50
    assert result["reasons"]
    assert result["why"]["supporting_factors"]
    assert result["suggested_stop"] is not None
    assert result["suggested_tp"] is not None
    assert result["autonomous_trading"] is False
    assert result["advisory_only"] is True


def test_portfolio_ai_empty() -> None:
    result = analyze_portfolio_ai([])
    assert result["status"] == "unavailable"
    assert result["autonomous_trading"] is False


def test_portfolio_ai_metrics() -> None:
    trades = [
        {"symbol": "EURUSD", "pnl": 20, "closed_at": "2024-01-02T10:00:00+00:00"},
        {"symbol": "EURUSD", "pnl": -10, "closed_at": "2024-01-02T14:00:00+00:00"},
        {"symbol": "GBPUSD", "pnl": 15, "closed_at": "2024-01-03T11:00:00+00:00"},
        {"symbol": "GBPUSD", "pnl": -5, "closed_at": "2024-01-03T15:00:00+00:00"},
    ]
    result = analyze_portfolio_ai(trades)
    assert result["status"] == "available"
    assert result["metrics"]["win_rate"] == 0.5
    assert result["sample_size"] == 4
    assert result["most_common_mistakes"]


def test_review_trade_labels() -> None:
    result = review_trade(
        {
            "symbol": "EURUSD",
            "pnl": 50,
            "entry_price": 1.1,
            "exit_price": 1.12,
            "stop_loss": 1.09,
        }
    )
    assert result["status"] == "available"
    assert "Good Entry" in result["labels"] or "TP Excellent" in result["labels"]
    assert result["autonomous_trading"] is False


def test_risk_ai_margin_flag() -> None:
    result = analyze_risk_ai(
        account={
            "equity": 1000,
            "balance": 1200,
            "margin": 800,
            "free_margin": 50,
            "leverage": 500,
        },
        positions=[
            {"symbol": "EURUSD", "volume": 1.5},
            {"symbol": "GBPUSD", "volume": 1.0},
            {"symbol": "AUDUSD", "volume": 0.5},
        ],
    )
    assert result["status"] == "available"
    assert result["overall"] in {"watch", "stressed"}
    codes = {f["code"] for f in result["flags"]}
    assert "margin_risk" in codes or "over_leveraged" in codes
    assert result["autonomous_trading"] is False


def test_execution_ai_from_attempts() -> None:
    attempts = [
        {"outcome": "success", "latency_ms": 40},
        {"outcome": "success", "latency_ms": 50},
        {"outcome": "rejected", "latency_ms": 30},
    ]
    fills = [{"slippage": 0.0001, "fill_price": 1.1, "requested_price": 1.0999}]
    result = analyze_execution_ai(attempts=attempts, fills=fills, broker_latency_ms=45)
    assert result["status"] == "available"
    assert result["execution_score"] is not None
    assert result["never_submits_orders"] is True
    assert result["autonomous_trading"] is False


def test_correlation_insufficient() -> None:
    result = correlation_from_closes({"EURUSD": [1.1, 1.2]})
    assert result["status"] == "unavailable"


def test_correlation_matrix() -> None:
    # correlated series
    a = [1.0 + i * 0.01 for i in range(30)]
    b = [2.0 + i * 0.02 for i in range(30)]
    c = [3.0 - i * 0.01 for i in range(30)]
    result = correlation_from_closes({"AAA": a, "BBB": b, "CCC": c})
    assert result["status"] == "available"
    assert len(result["labels"]) == 3
    assert len(result["matrix"]) == 3
    # AAA vs BBB should be strongly positive
    i = result["labels"].index("AAA")
    j = result["labels"].index("BBB")
    assert result["matrix"][i][j] is not None
    assert result["matrix"][i][j] > 0.9
