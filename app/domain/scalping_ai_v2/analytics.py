"""Performance analytics + post-trade intelligence."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.types import ModuleResult, ScalpCycleInput


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def build_performance_analytics(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    _ = config
    health = inp.health if isinstance(inp.health, dict) else {}
    metrics = health.get("analytics")
    if not isinstance(metrics, dict):
        metrics = health.get("analytics_metrics")
    closed = inp.closed_trade
    if not isinstance(metrics, dict) and not isinstance(closed, dict):
        return ModuleResult(
            module="performance_analytics",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="Await data",
            reasons=(
                "No analytics metrics supplied — never fabricates performance",
            ),
        )

    panels: dict[str, Any] = {}
    reasons: list[str] = []
    source = metrics if isinstance(metrics, dict) else {}
    keys = (
        "win_rate",
        "average_rr",
        "execution_latency",
        "spread",
        "slippage",
        "decision_quality",
        "risk_quality",
        "capital_preservation",
        "market_quality",
        "trade_quality",
    )
    for key in keys:
        if key in source:
            panels[key] = source[key]
            reasons.append(f"{key}={source[key]} (supplied)")
    if isinstance(closed, dict):
        for key in ("pnl", "rr", "slippage", "latency_ms"):
            if key in closed and key not in panels:
                panels[key] = closed[key]

    if not panels:
        return ModuleResult(
            module="performance_analytics",
            status="empty",
            score=None,
            passed=None,
            recommendation="Await data",
            reasons=("Analytics payload empty",),
        )

    score = Decimal("60")
    wr = _dec(panels.get("win_rate"))
    if wr is not None and wr >= Decimal("50"):
        score += Decimal("10")
    reasons.append("Analytics are observational — not a profit guarantee")
    return ModuleResult(
        module="performance_analytics",
        status="available",
        score=score,
        passed=True,
        recommendation="Monitor",
        reasons=tuple(reasons),
        details={"panels": panels, "promise_profitability": False},
    )


def build_post_trade_intelligence(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    _ = config
    trade = inp.closed_trade
    if not isinstance(trade, dict):
        return ModuleResult(
            module="post_trade_intelligence",
            status="empty",
            score=None,
            passed=None,
            recommendation="Await closed trade",
            reasons=("No closed trade — never invents reports",),
        )
    report = {
        "entry_reason": trade.get("entry_reason") or "not_supplied",
        "exit_reason": trade.get("exit_reason") or "not_supplied",
        "risk_summary": trade.get("risk_summary") or trade.get("risk") or {},
        "execution_summary": trade.get("execution_summary")
        or trade.get("execution")
        or {},
        "market_summary": trade.get("market_summary") or trade.get("market") or {},
        "lessons_learned": trade.get("lessons_learned") or [],
        "operator_notes": trade.get("operator_notes") or [],
        "rewrites_strategy_rules": False,
    }
    return ModuleResult(
        module="post_trade_intelligence",
        status="available",
        score=Decimal("70"),
        passed=True,
        recommendation="Review",
        reasons=(
            "Post-trade report generated from supplied closed trade",
            "Must never automatically change strategy rules",
        ),
        details=report,
    )


def build_observability_dashboard(
    *,
    modules: dict[str, dict[str, Any]],
    controller: dict[str, Any],
    watchdog: dict[str, Any],
    events_count: int,
) -> dict[str, Any]:
    return {
        "status": "available",
        "dashboards": {
            "auto_trading": controller,
            "market_quality": modules.get("market_quality_engine"),
            "decision_pipeline": {
                "risk": modules.get("dynamic_risk_engine_integration"),
                "safety_execution": modules.get("execution_quality_monitor"),
                "decision_note": "Uses existing Decision Center — never bypasses",
            },
            "execution": modules.get("execution_quality_monitor"),
            "broker": {
                "from_execution_monitor": modules.get(
                    "execution_quality_monitor", {}
                ).get("details")
            },
            "risk": modules.get("dynamic_risk_engine_integration"),
            "safety": {
                "note": "Existing Safety Engine authoritative",
                "execution_gate": modules.get("execution_quality_monitor"),
            },
            "system_health": watchdog,
            "latency": (
                modules.get("execution_quality_monitor", {})
                .get("details", {})
                .get("checks", {})
                .get("latency_acceptable")
            ),
            "recovery": modules.get("incident_recovery"),
            "incidents": modules.get("incident_recovery"),
        },
        "events_logged": events_count,
        "never_order_send": True,
    }
