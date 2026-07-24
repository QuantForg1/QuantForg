"""Live statistics dashboard data — observational only."""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def build_live_statistics() -> dict[str, Any]:
    """Aggregate today's performance / risk / execution metrics from existing stores."""
    stats: dict[str, Any] = {
        "todays_trades": None,
        "win_rate": None,
        "current_drawdown": None,
        "profit_factor": None,
        "average_rr": None,
        "daily_pnl": None,
        "weekly_pnl": None,
        "monthly_pnl": None,
        "execution_latency_ms": None,
        "slippage": None,
        "current_portfolio_risk": None,
        "ai_calibration": None,
    }

    try:
        from app.domain.institutional_trading.ai_validation import (
            get_execution_quality_monitor,
            get_portfolio_analytics_store,
            get_strategy_performance_store,
        )

        port = get_portfolio_analytics_store().snapshot()
        if isinstance(port, dict):
            stats["daily_pnl"] = port.get("daily_pnl", port.get("pnl_today"))
            stats["weekly_pnl"] = port.get("weekly_pnl", port.get("pnl_week"))
            stats["monthly_pnl"] = port.get("monthly_pnl", port.get("pnl_month"))
            stats["current_drawdown"] = port.get("drawdown", port.get("current_drawdown"))
            stats["profit_factor"] = port.get("profit_factor")
            stats["win_rate"] = port.get("win_rate")
            stats["todays_trades"] = port.get("trades_today", port.get("todays_trades"))
            stats["average_rr"] = port.get("average_rr", port.get("avg_rr"))

        strat = get_strategy_performance_store().snapshot()
        if isinstance(strat, dict) and stats["win_rate"] is None:
            by = strat.get("by_strategy") or {}
            if isinstance(by, dict) and by:
                # Aggregate first available
                first = next(iter(by.values()))
                if isinstance(first, dict):
                    stats["win_rate"] = stats["win_rate"] or first.get("win_rate")
                    stats["profit_factor"] = stats["profit_factor"] or first.get("profit_factor")
                    stats["average_rr"] = stats["average_rr"] or first.get("average_rr")

        eq = get_execution_quality_monitor().snapshot()
        if isinstance(eq, dict):
            stats["execution_latency_ms"] = eq.get("avg_latency_ms", eq.get("latency_ms"))
            stats["slippage"] = eq.get("avg_slippage", eq.get("slippage"))
    except Exception:
        logger.exception("live_stats_ai_validation_failed")

    try:
        from app.domain.institutional_trading.performance_lab import (
            get_calibration_store,
        )

        stats["ai_calibration"] = get_calibration_store().chart()
    except Exception:
        pass

    try:
        from app.domain.institutional_trading.portfolio_intelligence import (
            get_dynamic_risk_budget,
        )

        stats["current_portfolio_risk"] = get_dynamic_risk_budget().snapshot()
    except Exception:
        pass

    try:
        from app.domain.institutional_trading.production_hardening.performance import (
            get_live_performance_monitor,
        )

        mon = get_live_performance_monitor().snapshot()
        if isinstance(mon, dict):
            for k_src, k_dst in (
                ("win_rate", "win_rate"),
                ("profit_factor", "profit_factor"),
                ("drawdown", "current_drawdown"),
                ("trades_today", "todays_trades"),
                ("avg_rr", "average_rr"),
                ("daily_pnl", "daily_pnl"),
            ):
                if stats.get(k_dst) is None and mon.get(k_src) is not None:
                    stats[k_dst] = mon[k_src]
    except Exception:
        pass

    return {"live_statistics": stats, "source": "composed", "affects_production": False}
