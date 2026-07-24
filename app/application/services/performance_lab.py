"""Live Performance Lab dashboard — v8."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.performance_lab import (
    DEFAULT_LAB_CONFIG,
    build_symbol_rankings,
    compare_strategies,
    get_calibration_store,
    get_duel_store,
    get_opportunity_outcome_store,
    get_portfolio_heatmap_store,
    get_recommendation_engine,
    get_trade_replay_store,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_performance_lab_dashboard(
    *,
    symbol: str | None = None,
    session: str | None = None,
    regime: str | None = None,
    replay_id: str | None = None,
    frame_index: int = 0,
) -> dict[str, Any]:
    rankings = build_symbol_rankings()
    engine = get_recommendation_engine()
    # Refresh advisory recommendations from current rankings (never auto-apply)
    try:
        engine.generate_from_rankings(rankings)
    except Exception:
        logger.exception("lab_recommendations_failed")

    # Heatmap: try live positions from ITE runtime
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime
        from app.application.services.institutional_alpha_engine import (
            build_alpha_dashboard,
        )

        runtime = get_ite_runtime()
        positions: list[dict[str, Any]] = []
        if runtime is not None:
            for pos in (runtime.position_management.engine._positions or {}).values():
                positions.append(pos.to_dict() if hasattr(pos, "to_dict") else {"ticket": getattr(pos, "ticket", None)})
        alpha = {}
        try:
            mt5 = getattr(runtime, "mt5_adapter", None) if runtime else None
            alpha = build_alpha_dashboard(
                mt5_adapter=mt5,
                open_symbols=[str(p.get("symbol") or "") for p in positions],
            )
        except Exception:
            alpha = {}
        get_portfolio_heatmap_store().update_from_positions(
            positions,
            correlation=alpha.get("correlation_matrix"),
            confidence_by_symbol=alpha.get("ai_confidence_by_symbol"),
        )
    except Exception:
        logger.exception("lab_heatmap_update_failed")

    replay_step = None
    if replay_id:
        replay_step = get_trade_replay_store().step(replay_id, frame_index)

    return {
        "version": DEFAULT_LAB_CONFIG.version,
        "config": DEFAULT_LAB_CONFIG.to_dict(),
        "champion_vs_challenger": {
            "summary": get_duel_store().summary(),
            "recent": get_duel_store().recent(limit=40),
        },
        "confidence_calibration": get_calibration_store().chart(),
        "opportunity_replay": {
            "database_summary": get_opportunity_outcome_store().summary(),
            "recent_opportunities": get_opportunity_outcome_store().recent(limit=40),
            "trade_replays": get_trade_replay_store().list(limit=20),
            "step": replay_step,
        },
        "strategy_comparison": compare_strategies(
            symbol=symbol, session=session, regime=regime
        ),
        "portfolio_heatmap": get_portfolio_heatmap_store().snapshot(),
        "symbol_rankings": rankings,
        "adaptive_recommendations": engine.recent(limit=25),
        "safeguards": {
            "challenger_may_execute": False,
            "recommendations_auto_applied": False,
            "trading_logic_unchanged": True,
        },
    }
