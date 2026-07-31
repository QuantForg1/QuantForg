"""Daily institutional execution reporting — real aggregates only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_execution_daily_report() -> dict[str, Any]:
    """Daily production metrics from existing EQ / learning / analytics stores."""
    eq: dict[str, Any] = {}
    rich: dict[str, Any] = {}
    analytics: dict[str, Any] = {}
    learning: dict[str, Any] = {}

    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        eq = get_execution_quality_store().snapshot()
    except Exception:
        eq = {}

    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality_analytics import (  # noqa: E501
            get_execution_quality_analytics_store,
        )

        rich = get_execution_quality_analytics_store().snapshot()
    except Exception:
        rich = {}

    try:
        from app.domain.institutional_trading.ai_scalping.performance_analytics import (
            build_performance_analytics,
        )

        analytics = build_performance_analytics()
    except Exception:
        analytics = {}

    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        learning = get_scalping_learning_store().summary()
    except Exception:
        learning = {}

    # Approval / execution rates from EQ samples when present
    samples = int(eq.get("samples") or 0)
    fill_rate = eq.get("fill_rate")
    reject_rate = eq.get("reject_rate")

    # Best / worst symbols from learning (real only)
    best_symbol = analytics.get("best_symbol")
    worst_symbol = analytics.get("worst_symbol")

    # Uptime proxies from live health if available (never invent 100%)
    gateway_uptime = None
    broker_uptime = None
    try:
        from app.domain.institutional_trading.ai_scalping.live_health import (
            get_live_health_monitor,
        )

        health = get_live_health_monitor().snapshot()
        if isinstance(health, dict):
            gateway_uptime = health.get("gateway_uptime_pct") or health.get(
                "gateway_ok"
            )
            broker_uptime = health.get("mt5_uptime_pct") or health.get("mt5_connected")
    except Exception:
        pass

    return {
        "as_of": _iso(),
        "execution_quality": rich.get("avg_execution_score") or eq.get(
            "execution_success_rate"
        ),
        "average_latency_ms": rich.get("avg_latency_ms") or eq.get("avg_latency_ms"),
        "average_slippage": rich.get("avg_slippage") or eq.get("avg_slippage"),
        "broker_uptime": broker_uptime,
        "gateway_uptime": gateway_uptime,
        "ai_approval_rate": None,  # never fabricate from unrelated metrics
        "trade_approval_rate": None,  # never fabricate
        "trade_execution_rate": fill_rate,
        "reject_rate": reject_rate,
        "samples": samples,
        "best_symbols": [best_symbol] if best_symbol else [],
        "worst_symbols": [worst_symbol] if worst_symbol else [],
        "learning_trades": learning.get("trades"),
        "fabricated": False,
        "source": "existing_eq_learning_analytics_only",
        "observe_only": True,
    }
