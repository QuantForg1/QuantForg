"""Execution Readiness — advisory only; never creates execution paths."""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def evaluate_execution_readiness(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    reasons: list[str] = []
    has_any = any(
        v is not None
        for v in (
            inp.execution_mode,
            inp.spread,
            inp.risk_engine_passed,
            inp.safety_engine_passed,
        )
    )
    if not has_any:
        return ModuleResult(
            module="execution_readiness",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No execution readiness facts — never invents gateway state",
                "Existing Execution Pipeline remains the only path",
            ),
            details={},
        )

    score = Decimal("50")
    mode = (inp.execution_mode or "").upper()
    if mode in {"HALTED", "OFFLINE", "DISCONNECTED"}:
        score = Decimal("0")
        reasons.append(f"Mode {mode} — not ready")
    elif mode in {"SHADOW", "PAPER"}:
        score = Decimal("45")
        reasons.append(f"Mode {mode} — advisory only, no live send")
    elif mode:
        score = Decimal("70")
        reasons.append(f"Mode {mode} observed")
    else:
        reasons.append("Execution mode not supplied")

    if inp.spread is not None:
        if inp.spread > config.max_spread:
            score = min(score, Decimal("20"))
            reasons.append(f"Spread {inp.spread} blocks readiness")
        else:
            score += Decimal("10")
            reasons.append(f"Spread {inp.spread} acceptable for readiness")

    if inp.risk_engine_passed is not True:
        score = min(score, Decimal("30"))
        reasons.append("Risk Engine not passed — readiness fail-closed")
    if inp.safety_engine_passed is not True:
        score = min(score, Decimal("30"))
        reasons.append("Safety Engine not passed — readiness fail-closed")

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    passed = (
        score >= config.min_execution_readiness
        and inp.risk_engine_passed is True
        and inp.safety_engine_passed is True
        and mode not in {"HALTED", "OFFLINE", "DISCONNECTED"}
    )
    reasons.append("Does not call order_send or create alternate paths")
    reasons.append("Uses existing Execution Pipeline when operator executes")
    return ModuleResult(
        module="execution_readiness",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons),
        details={
            "execution_mode": mode or None,
            "min_execution_readiness": str(config.min_execution_readiness),
            "never_order_send": True,
            "alternate_execution_path": False,
        },
    )
