"""Portfolio Intelligence executive dashboard — v9."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.portfolio_intelligence import (
    DEFAULT_PI_CONFIG,
    evaluate_portfolio,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_portfolio_intelligence_dashboard() -> dict[str, Any]:
    opportunities: list[dict[str, Any]] = []
    equity = 0.0
    free_margin = 0.0
    daily_pnl = 0.0
    weekly_pnl = 0.0
    monthly_pnl = 0.0
    drawdown = 0.0
    open_symbols: list[str] = []
    exposure: dict[str, float] = {}
    corr: dict[str, Any] = {}
    session = "unknown"
    exec_q = 0.7

    try:
        from app.application.services.institutional_alpha_engine import (
            build_alpha_dashboard,
        )
        from app.application.services.institutional_ite_runtime import get_ite_runtime
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        runtime = get_ite_runtime()
        plane = get_control_plane()
        positions = []
        if runtime is not None:
            for pos in (runtime.position_management.engine._positions or {}).values():
                d = pos.to_dict() if hasattr(pos, "to_dict") else {}
                positions.append(d)
                sym = str(d.get("symbol") or getattr(pos, "symbol", "") or "")
                if sym:
                    open_symbols.append(sym)
                    exposure[sym] = exposure.get(sym, 0.0) + float(
                        d.get("remaining_volume") or getattr(pos, "remaining_volume", 0) or 0
                    )
        mt5 = getattr(runtime, "mt5_adapter", None) if runtime else None
        alpha = build_alpha_dashboard(mt5_adapter=mt5, open_symbols=open_symbols)
        opportunities = list(alpha.get("opportunity_ranking") or [])
        corr = dict(alpha.get("correlation_matrix") or {})
        perf = dict(alpha.get("performance") or alpha.get("analytics") or {})
        daily_pnl = float(perf.get("daily_pnl") or 0)
        weekly_pnl = float(perf.get("weekly_pnl") or 0)
        monthly_pnl = float(perf.get("monthly_pnl") or 0)

        # Equity from last cycle account if available
        last = getattr(runtime, "_last_cycle", None) if runtime else None
        _ = last
        try:
            from app.application.services.auto_trading_status import build_status_facts
            from core.config.settings import get_settings

            facts, live = build_status_facts(plane, settings=get_settings())
            equity = float(live.get("equity") or facts.equity or 0) if hasattr(facts, "equity") else float(live.get("equity") or 0)
            free_margin = float(live.get("free_margin") or live.get("margin_free") or 0)
            session = str(live.get("session") or "unknown")
        except Exception:
            equity = float(sum(exposure.values()) * 1000) if exposure else 100_000.0

        try:
            from app.domain.institutional_trading.ai_validation import (
                get_execution_quality_monitor,
                get_portfolio_analytics_store,
            )

            pa = get_portfolio_analytics_store().snapshot()
            drawdown = float(pa.get("current_drawdown_pct") or 0)
            if pa.get("equity"):
                equity = float(pa["equity"])
            eq_mon = get_execution_quality_monitor().snapshot()
            # Normalize execution quality 0–1 from inverse latency
            lat = eq_mon.get("avg_total_execution_ms")
            if lat:
                exec_q = max(0.2, min(1.0, 1.0 - float(lat) / 5000.0))
        except Exception:
            pass
    except Exception:
        logger.exception("portfolio_intelligence_dashboard_gather_failed")
        if not opportunities:
            opportunities = []

    result = evaluate_portfolio(
        opportunities=opportunities,
        equity=equity or 100_000.0,
        free_margin=free_margin,
        open_symbols=open_symbols,
        exposure_by_symbol=exposure,
        daily_pnl=daily_pnl,
        weekly_pnl=weekly_pnl,
        monthly_pnl=monthly_pnl,
        current_drawdown_pct=drawdown,
        portfolio_volatility=0.0,
        correlation_matrix=corr,
        session=session,
        execution_quality_score=exec_q,
    )
    result["config"] = DEFAULT_PI_CONFIG.to_dict()
    return result
