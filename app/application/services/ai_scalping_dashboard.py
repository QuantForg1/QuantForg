"""Institutional AI Scalping v6.1 executive dashboard — read-only metrics."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.institutional_trading.ai_scalping import (
    DEFAULT_AI_SCALPING_CONFIG,
    compare_backtest_vs_live,
    get_scalping_diagnostics_store,
    get_scalping_learning_store,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_ai_scalping_dashboard() -> dict[str, Any]:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    current: dict[str, Any] = {}
    try:
        from app.application.services.ai_scalping_mode import current_mode_snapshot
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        current = current_mode_snapshot(get_ite_runtime())
    except Exception:
        logger.exception("ai_scalping_dashboard_mode_failed")

    ai_score = current.get("ai_score") if isinstance(current, dict) else None
    if not isinstance(ai_score, dict):
        ai_score = {}

    diagnostics = get_scalping_diagnostics_store()
    learning = None
    with contextlib.suppress(Exception):
        learning = get_scalping_learning_store().summary()

    live_metrics: dict[str, Any] = {}
    backtest_metrics: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.production_hardening.performance import (
            get_live_performance_monitor,
        )

        live_metrics = get_live_performance_monitor().snapshot() or {}
    except Exception:  # noqa: S110
        pass
    try:
        from app.domain.institutional_trading.production_hardening.backtest_live import (  # noqa: E501
            get_backtest_live_store,
        )

        bt = get_backtest_live_store().snapshot()
        if isinstance(bt, dict):
            backtest_metrics = bt.get("backtest") or bt.get("latest_backtest") or {}
    except Exception:  # noqa: S110
        pass

    validation = compare_backtest_vs_live(
        backtest=backtest_metrics if isinstance(backtest_metrics, dict) else {},
        live=live_metrics if isinstance(live_metrics, dict) else {},
    )

    execution_quality: dict[str, Any] = {}
    post_trade: dict[str, Any] = {}
    health: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        execution_quality = get_execution_quality_store().snapshot()
    with contextlib.suppress(Exception):
        from app.domain.institutional_trading.ai_scalping.post_trade_analytics import (
            get_post_trade_journal,
        )

        journal = get_post_trade_journal()
        post_trade = {
            "performance": journal.performance_snapshot(),
            "recent": journal.recent(limit=25),
        }
    with contextlib.suppress(Exception):
        from app.domain.institutional_trading.ai_scalping.live_health import (
            get_live_health_monitor,
        )

        health = get_live_health_monitor().snapshot()

    perf = post_trade.get("performance") if isinstance(post_trade, dict) else {}
    if not isinstance(perf, dict):
        perf = {}

    performance_metrics = {
        "win_rate": perf.get("win_rate") or live_metrics.get("win_rate"),
        "average_r": perf.get("average_r"),
        "profit_factor": perf.get("profit_factor"),
        "average_hold_time": perf.get("average_hold_minutes"),
        "average_latency": (
            execution_quality.get("avg_latency_ms")
            or live_metrics.get("avg_execution_latency_ms")
        ),
        "execution_success_rate": execution_quality.get("execution_success_rate"),
        "expectancy": perf.get("expectancy"),
        "fill_rate": execution_quality.get("fill_rate"),
        "reject_rate": execution_quality.get("reject_rate"),
        "requote_rate": execution_quality.get("requote_rate"),
        "partial_fill_rate": execution_quality.get("partial_fill_rate"),
        "avg_slippage": execution_quality.get("avg_slippage")
        or live_metrics.get("avg_slippage"),
    }

    setup = {
        "direction": ai_score.get("direction"),
        "confidence": ai_score.get("ai_confidence"),
        "reason": (
            ai_score.get("reject_reason")
            or "; ".join((ai_score.get("reasons") or [])[-3:])
            or None
        ),
        "expected_hold_time": ai_score.get("expected_hold_time"),
        "expected_rr": ai_score.get("expected_rr"),
        "entry": ai_score.get("entry"),
        "stop_loss": ai_score.get("stop_loss"),
        "take_profit": ai_score.get("take_profit"),
        "momentum": ai_score.get("momentum"),
        "liquidity": ai_score.get("liquidity"),
        "structure": ai_score.get("structure_score"),
        "buy_score": ai_score.get("buy_score"),
        "sell_score": ai_score.get("sell_score"),
        "reject": ai_score.get("reject"),
        "quality_checks": ai_score.get("quality_checks"),
        "regime_execution": ai_score.get("regime_execution"),
    }

    return {
        "version": cfg.version,
        "config": cfg.to_dict(),
        "mission": (
            "Institutional AI scalping v6.1 — execution hardening. "
            "Quality over quantity. No strategy mutation. No risk increase."
        ),
        "current_setup": setup,
        "mode": current,
        "diagnostics": {
            "summary": diagnostics.summary(),
            "recent": diagnostics.recent(limit=40),
        },
        "learning": learning,
        "validation": validation,
        "performance_metrics": performance_metrics,
        "execution_quality": execution_quality,
        "post_trade": post_trade,
        "live_health": health,
        "universe": list(cfg.universe),
        "safeguards": {
            "allow_martingale": False,
            "allow_grid": False,
            "never_prefer_buy_only": True,
            "risk_increase_locked": True,
            "risk_per_trade_pct": str(cfg.risk_per_trade_pct),
            "broker_safety_intact": True,
            "self_protection_enabled": cfg.self_protection_enabled,
            "slippage_protection_enabled": cfg.slippage_protection_enabled,
            "volatility_adjusted_sizing": cfg.volatility_adjusted_sizing,
        },
    }
