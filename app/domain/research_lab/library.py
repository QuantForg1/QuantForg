"""Research Lab — independent strategy modules (catalog metadata only)."""

from __future__ import annotations

from typing import Any

# Research library: engine plugins + research archetypes (no fabricated performance).
STRATEGY_LIBRARY: list[dict[str, Any]] = [
    {
        "key": "trend_following",
        "name": "Trend Following",
        "family": "trend",
        "engine_plugin": True,
        "best_regimes": ["Trending", "Low Volatility"],
        "description": "Follows directional bias with EMA/structure continuation",
    },
    {
        "key": "liquidity_sweep",
        "name": "Liquidity Sweep",
        "family": "smart_money",
        "engine_plugin": False,
        "best_regimes": ["Range / mixed", "High Volatility"],
        "description": "Research archetype — sweep of obvious highs/lows then reversal",
    },
    {
        "key": "breakout",
        "name": "Breakout",
        "family": "breakout",
        "engine_plugin": True,
        "best_regimes": ["Trending", "High Volatility"],
        "description": "Range expansion breakout with volume/structure confirmation",
    },
    {
        "key": "mean_reversion",
        "name": "Mean Reversion",
        "family": "mean_reversion",
        "engine_plugin": True,
        "best_regimes": ["Range / mixed", "Low Volatility"],
        "description": "Fade stretched extensions toward mean",
    },
    {
        "key": "momentum",
        "name": "Momentum",
        "family": "momentum",
        "engine_plugin": True,
        "best_regimes": ["Trending", "High Volatility"],
        "description": "Rides accelerating moves once impulse confirms",
    },
    {
        "key": "session_breakout",
        "name": "Session Breakout",
        "family": "session",
        "engine_plugin": False,
        "best_regimes": ["Trending", "News Driven"],
        "description": "Research archetype — London/NY session range break",
    },
    {
        "key": "order_block",
        "name": "Order Block",
        "family": "smart_money",
        "engine_plugin": False,
        "best_regimes": ["Trending", "Range / mixed"],
        "description": "Research archetype — institutional order block retests",
    },
    {
        "key": "fvg",
        "name": "Fair Value Gap",
        "family": "smart_money",
        "engine_plugin": False,
        "best_regimes": ["Trending", "High Volatility"],
        "description": "Research archetype — FVG fill / continuation",
    },
    {
        "key": "ma_cross",
        "name": "MA Cross",
        "family": "trend",
        "engine_plugin": True,
        "best_regimes": ["Trending"],
        "description": "Classic moving-average cross system",
    },
    {
        "key": "rsi",
        "name": "RSI",
        "family": "momentum",
        "engine_plugin": True,
        "best_regimes": ["Range / mixed", "Mean Reversion"],
        "description": "RSI threshold / divergence research profile",
    },
    {
        "key": "macd",
        "name": "MACD",
        "family": "momentum",
        "engine_plugin": True,
        "best_regimes": ["Trending"],
        "description": "MACD signal-line / histogram research profile",
    },
    {
        "key": "bollinger",
        "name": "Bollinger",
        "family": "mean_reversion",
        "engine_plugin": True,
        "best_regimes": ["Range / mixed", "Low Volatility"],
        "description": "Band mean reversion / squeeze expansion",
    },
    {
        "key": "custom_rules",
        "name": "Custom Strategies",
        "family": "custom",
        "engine_plugin": True,
        "best_regimes": ["Trending", "Range / mixed"],
        "description": "User-defined rule tree for research experiments",
    },
]


def list_strategy_library() -> list[dict[str, Any]]:
    return [dict(s) for s in STRATEGY_LIBRARY]


def get_strategy(key: str) -> dict[str, Any] | None:
    k = key.strip().lower()
    for s in STRATEGY_LIBRARY:
        if s["key"] == k:
            return dict(s)
    return None
