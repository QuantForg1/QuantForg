"""Diagnostics center + operator dashboard for Scalping AI V2.1."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.scalping_ai_v2.types import ModuleResult


def build_diagnostics_center(
    *,
    modules: dict[str, Any],
    stability: dict[str, Any] | None = None,
    latency: dict[str, Any] | None = None,
    emergency: dict[str, Any] | None = None,
    safe_mode: dict[str, Any] | None = None,
    state_store: dict[str, Any] | None = None,
    audit_count: int = 0,
    event_bus_count: int = 0,
) -> ModuleResult:
    panels = {
        "broker": _panel(modules, "execution_quality_monitor", "broker"),
        "gateway": _panel(modules, "execution_quality_monitor", "gateway"),
        "risk": _panel(modules, "dynamic_risk_engine_integration"),
        "safety": _panel(modules, "execution_quality_monitor", "safety"),
        "decision": _panel(modules, "opportunity_ranking_engine"),
        "execution": _panel(modules, "execution_quality_monitor"),
        "analytics": _panel(modules, "performance_analytics"),
        "database": (safe_mode or {}).get("reasons"),
        "memory": (stability or {}).get("sample", {}).get("memory_mb"),
        "cpu": (stability or {}).get("sample", {}).get("cpu_pct"),
        "latency": (latency or {}).get("distributions") or latency,
        "watchdog": _panel(modules, "production_watchdog"),
        "recovery": _panel(modules, "incident_recovery"),
        "auto_trading": _panel(modules, "continuous_auto_trading_controller"),
        "supervisor": _panel(modules, "active_trade_supervisor"),
        "event_bus": {"events": event_bus_count},
        "state_store": state_store or {},
        "emergency_stop": emergency or {},
        "safe_mode": safe_mode or {},
    }
    scores: list[Decimal] = []
    for _key, mod in modules.items():
        if not isinstance(mod, dict):
            continue
        raw = mod.get("score")
        if raw is None:
            continue
        try:
            scores.append(Decimal(str(raw)))
        except (InvalidOperation, ValueError, TypeError):
            continue
    health_score = (
        (sum(scores) / Decimal(len(scores))).quantize(Decimal("0.01"))
        if scores
        else None
    )
    emergency_armed = bool((emergency or {}).get("armed"))
    in_safe = bool((safe_mode or {}).get("safe_mode"))
    if emergency_armed or in_safe:
        recommendation = "Degraded"
    elif health_score is not None and health_score >= Decimal("70"):
        recommendation = "Healthy"
    else:
        recommendation = "Monitor"

    return ModuleResult(
        module="production_diagnostics",
        status="available",
        score=health_score,
        passed=not emergency_armed and not in_safe,
        recommendation=recommendation,
        reasons=(
            f"Health score {health_score}" if health_score is not None else "No scores",
            f"Audit entries {audit_count}",
            "Diagnostics are observational — not a profit guarantee",
        ),
        details={
            "panels": panels,
            "health_score": str(health_score) if health_score is not None else None,
            "panel_keys": list(panels.keys()),
        },
    )


def build_operator_dashboard(
    *,
    recommendation: str,
    modules: dict[str, Any],
    emergency: dict[str, Any] | None = None,
    safe_mode: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    stability: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ranking = modules.get("opportunity_ranking_engine") or {}
    mq = modules.get("market_quality_engine") or {}
    controller = modules.get("continuous_auto_trading_controller") or {}
    risk = modules.get("dynamic_risk_engine_integration") or {}
    analytics = modules.get("performance_analytics") or {}
    recovery = modules.get("incident_recovery") or {}
    watchdog = modules.get("production_watchdog") or {}

    return {
        "auto_trading_status": (controller.get("details") or {}).get(
            "run_state", controller.get("recommendation")
        ),
        "current_state": {
            "recommendation": recommendation,
            "safe_mode": bool((safe_mode or {}).get("safe_mode")),
            "emergency_stop": bool((emergency or {}).get("armed")),
            "state_store": (state or {}).get("auto_trading_state"),
        },
        "current_opportunity": (ranking.get("details") or {}).get("selected"),
        "market_quality": {
            "score": mq.get("score"),
            "recommendation": mq.get("recommendation"),
        },
        "open_positions": (state or {}).get("open_positions") or [],
        "risk_usage": risk.get("details") or {},
        "todays_statistics": analytics.get("details") or {},
        "health": {
            "watchdog": watchdog.get("recommendation"),
            "diagnostics": (diagnostics or {}).get("recommendation"),
            "stability": stability,
        },
        "incidents": (state or {}).get("active_incidents") or [],
        "recoveries": recovery.get("details") or {},
        "never_order_send": True,
        "promise_profitability": False,
    }


def _panel(
    modules: dict[str, Any], key: str, hint: str | None = None
) -> dict[str, Any]:
    row = modules.get(key)
    if not isinstance(row, dict):
        return {"status": "unavailable", "hint": hint}
    return {
        "status": row.get("status"),
        "score": row.get("score"),
        "recommendation": row.get("recommendation"),
        "hint": hint,
    }
