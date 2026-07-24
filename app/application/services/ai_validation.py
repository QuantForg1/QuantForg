"""AI Validation dashboard aggregator — v7."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_validation import (
    DEFAULT_AI_VALIDATION_CONFIG,
    get_benchmark_store,
    get_execution_quality_monitor,
    get_opportunity_history_store,
    get_portfolio_analytics_store,
    get_shadow_store,
    get_slippage_store,
    get_strategy_performance_store,
    get_validation_alerter,
    get_weight_optimizer,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_ai_validation_dashboard(*, replay_day: str | None = None) -> dict[str, Any]:
    strategy = get_strategy_performance_store().snapshot()
    portfolio = get_portfolio_analytics_store().snapshot()
    exec_q = get_execution_quality_monitor().snapshot()
    slip = get_slippage_store().snapshot()
    shadow = get_shadow_store()
    alerter = get_validation_alerter()

    # Feed alerts from current snapshots (idempotent soft checks)
    try:
        combined = strategy.get("combined") or {}
        alerter.on_win_rate(combined.get("win_rate"))
        alerter.on_drawdown(portfolio.get("current_drawdown_pct"))
        if exec_q.get("avg_total_execution_ms") is not None:
            alerter.on_latency_spike(latency_ms=float(exec_q["avg_total_execution_ms"]))
    except Exception:
        logger.exception("ai_validation_alert_eval_failed")

    # Sync QuantForg leg of benchmarks from portfolio monthly return when available
    try:
        bench = get_benchmark_store()
        if portfolio.get("monthly_return_pct") is not None:
            bench.update(quantforg=float(portfolio["monthly_return_pct"]))
    except Exception:
        pass

    return {
        "version": DEFAULT_AI_VALIDATION_CONFIG.version,
        "config": DEFAULT_AI_VALIDATION_CONFIG.to_dict(),
        "strategy_performance": strategy,
        "performance_trends": strategy,
        "strategy_comparison": strategy.get("by_strategy", {}),
        "execution_quality": exec_q,
        "slippage_report": slip,
        "ai_validation_report": {
            "summary": shadow.summary(),
            "recent_comparisons": shadow.recent(limit=40),
        },
        "opportunity_replay": get_opportunity_history_store().replay(replay_day),
        "risk_overview": {
            "portfolio": portfolio,
            "alerts": alerter.recent(limit=30),
        },
        "portfolio_analytics": portfolio,
        "weight_optimizer": get_weight_optimizer().snapshot(),
        "benchmarks": get_benchmark_store().snapshot(),
        "alerts": alerter.recent(limit=50),
    }
