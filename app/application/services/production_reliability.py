"""Production Reliability dashboard — aggregates hardening + existing health."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.production_hardening import (
    DEFAULT_HARDENING_CONFIG,
    audit_secret_exposure,
    get_backtest_live_store,
    get_explainability_store,
    get_learning_weight_store,
    get_lifecycle_store,
    get_live_performance_monitor,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _component_status(ok: bool | None, *, warn: bool = False) -> str:
    if ok is True:
        return "Healthy"
    if warn or ok is None:
        return "Warning"
    return "Offline"


def build_production_reliability_dashboard() -> dict[str, Any]:
    from app.application.services.auto_trading_status import build_status_facts
    from app.application.services.institutional_alpha_engine import (
        build_alpha_dashboard,
        get_alpha_config,
    )
    from app.application.services.institutional_ite_runtime import get_ite_runtime
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from core.config.settings import get_settings

    plane = get_control_plane()
    settings = get_settings()
    facts, live = build_status_facts(plane, settings=settings)
    runtime = get_ite_runtime()

    gateway_ok = bool(live.get("gateway_connected") or facts.gateway_connected)
    broker_ok = bool(live.get("broker_connected") or facts.broker_connected)
    market_ok = bool(facts.market_data_live)
    auto_ok = bool(plane.auto_trading_enabled) and not plane.kill_switch_armed
    db_ok = True
    try:
        if runtime is not None:
            probes = runtime.probes.collect()
            db_ok = bool(probes.supabase_up)
    except Exception:
        db_ok = False

    oms_ok = plane.oms_orders_allowed()
    ai_ok = True  # decision pipeline is in-process
    railway_ok = True

    health = {
        "mt5_gateway": _component_status(gateway_ok),
        "broker": _component_status(broker_ok),
        "oms": _component_status(oms_ok, warn=not oms_ok and plane.mode.value == "SHADOW"),
        "auto_trading": _component_status(auto_ok, warn=plane.auto_trading_run_state == "paused"),
        "ai_engine": _component_status(ai_ok),
        "market_data": _component_status(market_ok),
        "database": _component_status(db_ok),
        "railway_service": _component_status(railway_ok),
    }

    perf = get_live_performance_monitor().snapshot()
    # Merge alpha analytics when available
    try:
        from app.domain.institutional_trading.alpha_engine.analytics import (
            get_alpha_analytics_store,
        )

        alpha_sum = get_alpha_analytics_store().summary()
        if perf.get("win_rate") is None and alpha_sum.get("win_rate") is not None:
            perf["win_rate"] = alpha_sum.get("win_rate")
        if not perf.get("daily_pnl") and alpha_sum.get("daily_pnl") is not None:
            perf["daily_pnl"] = alpha_sum.get("daily_pnl")
            perf["weekly_pnl"] = alpha_sum.get("weekly_pnl")
            perf["monthly_pnl"] = alpha_sum.get("monthly_pnl")
    except Exception:
        pass

    open_positions: list[dict[str, Any]] = []
    risk_exposure = None
    try:
        if runtime is not None and hasattr(runtime.position_management, "engine"):
            for pos in (runtime.position_management.engine._positions or {}).values():
                open_positions.append(pos.to_dict() if hasattr(pos, "to_dict") else {"ticket": pos.ticket})
    except Exception:
        logger.exception("open_positions_snapshot_failed")

    alpha = {}
    try:
        mt5 = getattr(runtime, "mt5_adapter", None) if runtime else None
        alpha = build_alpha_dashboard(
            mt5_adapter=mt5,
            open_symbols=[str(p.get("symbol") or "") for p in open_positions],
        )
    except Exception:
        alpha = {"enabled": get_alpha_config().enabled, "opportunity_ranking": []}

    incidents: list[dict[str, Any]] = []
    try:
        from app.domain.institutional_trading.reliability.models import IncidentStatus
        from app.domain.institutional_trading.reliability.platform import (
            get_reliability_platform,
        )

        rows = get_reliability_platform().incidents.list(limit=50)
        incidents = [
            i.to_dict()
            for i in rows
            if getattr(i, "status", None) is not IncidentStatus.RESOLVED
        ]
    except Exception:
        incidents = []

    compare = get_backtest_live_store().snapshot()
    # Refresh live side of comparison from performance
    try:
        get_backtest_live_store().upsert(
            "production",
            live_win_rate=perf.get("win_rate"),
        )
        compare = get_backtest_live_store().snapshot()
    except Exception:
        pass

    return {
        "version": DEFAULT_HARDENING_CONFIG.version,
        "config": DEFAULT_HARDENING_CONFIG.to_dict(),
        "system_health": health,
        "live_performance": perf,
        "opportunity_ranking": alpha.get("opportunity_ranking", []),
        "open_positions": open_positions,
        "risk_exposure": {
            "open_count": len(open_positions),
            "daily_loss_exceeded": plane.daily_loss_exceeded,
            "kill_switch": plane.kill_switch_armed,
            "max_open": plane.max_open_trades,
            "risk_per_trade_pct": str(plane.risk_per_trade_pct),
        },
        "daily_drawdown": {
            "daily_loss_exceeded": plane.daily_loss_exceeded,
            "max_daily_loss_pct": str(plane.max_daily_loss_pct),
        },
        "ai_confidence": alpha.get("ai_confidence_by_symbol", {}),
        "execution_timeline": get_lifecycle_store().recent(limit=80),
        "broker_status": health["broker"],
        "gateway_status": health["mt5_gateway"],
        "mt5_status": health["broker"],
        "portfolio_correlation": alpha.get("correlation_matrix", {}),
        "learning_status": get_learning_weight_store().snapshot(),
        "explanations": get_explainability_store().recent(limit=20),
        "incidents": incidents,
        "backtest_vs_live": compare,
        "secrets_audit": audit_secret_exposure(),
        "ops": {
            "mode": plane.mode.value,
            "auto_trading_run_state": plane.auto_trading_run_state,
            "trading_mode": getattr(plane, "trading_mode", "swing"),
            "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        },
    }
