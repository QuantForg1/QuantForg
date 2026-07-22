"""Risk integration + Execution Quality Monitor — never bypass engines."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.types import ModuleResult, ScalpCycleInput


def integrate_dynamic_risk(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    """Advisory sizing using existing risk policies — Risk Engine authoritative."""
    reasons: list[str] = []
    if inp.risk_engine_passed is None and inp.equity is None:
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No risk facts — never bypasses existing Risk Engine",
            ),
        )

    risk_pct = config.base_risk_pct
    if inp.consecutive_losses:
        risk_pct = risk_pct - (
            Decimal(inp.consecutive_losses) * Decimal("0.10")
        )
    if inp.daily_loss_pct is not None and inp.daily_loss_pct > 0:
        risk_pct = risk_pct - (inp.daily_loss_pct * Decimal("0.05"))
    risk_pct = max(risk_pct, config.risk_floor_pct)

    reasons.append(f"Advisory risk% {risk_pct} (floor {config.risk_floor_pct})")
    reasons.append("Existing Risk Engine remains authoritative")

    if inp.risk_engine_passed is False:
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="available",
            score=Decimal("0"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                *reasons,
                "Risk Engine rejected — never bypass",
            ),
            details={"risk_pct": str(risk_pct), "risk_engine_passed": False},
        )
    if inp.risk_engine_passed is None:
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="available",
            score=Decimal("20"),
            passed=False,
            recommendation="No Trade",
            reasons=(*reasons, "Risk Engine not assessed — fail closed"),
            details={"risk_pct": str(risk_pct), "risk_engine_passed": None},
        )

    if (
        inp.daily_loss_pct is not None
        and inp.daily_loss_pct >= config.max_daily_loss_pct
    ):
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="available",
            score=Decimal("10"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                *reasons,
                f"Daily loss {inp.daily_loss_pct}% >= max {config.max_daily_loss_pct}",
            ),
            details={"risk_pct": str(risk_pct)},
        )
    if inp.trades_today is not None and inp.trades_today >= config.max_trades_per_day:
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="available",
            score=Decimal("15"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                *reasons,
                f"Trades today {inp.trades_today} >= max {config.max_trades_per_day}",
            ),
            details={"risk_pct": str(risk_pct)},
        )
    if (
        inp.open_exposure_pct is not None
        and inp.open_exposure_pct >= config.max_open_exposure_pct
    ):
        return ModuleResult(
            module="dynamic_risk_engine_integration",
            status="available",
            score=Decimal("15"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                *reasons,
                f"Exposure {inp.open_exposure_pct}% >= max "
                f"{config.max_open_exposure_pct}",
            ),
            details={"risk_pct": str(risk_pct)},
        )

    # Advisory SL/TP placeholders from ATR when supplied — not invented otherwise.
    details: dict[str, Any] = {
        "risk_pct": str(risk_pct),
        "risk_engine_passed": True,
        "position_size": "deferred_to_risk_engine",
        "stop_loss": str(inp.atr) if inp.atr is not None else None,
        "take_profit": (
            str(inp.atr * Decimal("1.5")) if inp.atr is not None else None
        ),
        "exposure": (
            str(inp.open_exposure_pct)
            if inp.open_exposure_pct is not None
            else None
        ),
    }
    reasons.append("Position size / SL / TP deferred to existing Risk policies")
    return ModuleResult(
        module="dynamic_risk_engine_integration",
        status="available",
        score=Decimal("80"),
        passed=True,
        recommendation="Proceed",
        reasons=tuple(reasons),
        details=details,
    )


def monitor_execution_quality(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    """Pre-execution checks — reject safely if any fail."""
    checks = {
        "broker_connected": inp.broker_connected,
        "gateway_healthy": inp.gateway_healthy,
        "spread_acceptable": (
            None
            if inp.spread is None
            else inp.spread <= config.max_spread
        ),
        "market_open": inp.market_open,
        "margin_available": inp.margin_available,
        "risk_approved": inp.risk_engine_passed,
        "safety_approved": inp.safety_engine_passed,
        "decision_approved": (
            inp.decision_approved
            if inp.decision_approved is not None
            else (
                str((inp.decision_center or {}).get("decision") or "").upper()
                == "APPROVE"
                if inp.decision_center
                else None
            )
        ),
        "latency_acceptable": (
            None
            if inp.latency_ms is None
            else inp.latency_ms
            <= (inp.max_latency_ms or Decimal("500"))
        ),
    }
    if all(v is None for v in checks.values()):
        return ModuleResult(
            module="execution_quality_monitor",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No execution readiness facts — never invents gateway state",
                "Existing Execution Pipeline remains single source of truth",
            ),
        )

    reasons: list[str] = []
    failed: list[str] = []
    for name, val in checks.items():
        if val is None:
            reasons.append(f"{name}: not supplied")
            failed.append(name)
        elif val is False:
            reasons.append(f"{name}: FAILED")
            failed.append(name)
        else:
            reasons.append(f"{name}: ok")

    passed = len(failed) == 0
    reasons.append("Never creates alternate execution paths")
    reasons.append("Reject execution safely when any check fails")
    score = (
        Decimal("100")
        if passed
        else Decimal(max(0, 100 - 12 * len(failed)))
    )
    return ModuleResult(
        module="execution_quality_monitor",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons),
        details={"checks": checks, "failed": failed},
    )
