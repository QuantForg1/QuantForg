"""Operator Advisor — capital-preservation focused guidance."""

from __future__ import annotations

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def advise_operator(
    inp: BrainInput,
    config: TradingBrainConfig,
    *,
    recommendation: str,
    module_reasons: list[str],
) -> ModuleResult:
    advice: list[str] = []
    if recommendation == "No Trade":
        advice.append("Stand down — conditions do not support a disciplined entry")
        advice.append("Capital preservation over forced participation")
    else:
        advice.append(
            "Proceed only through existing Decision Center → Execution Pipeline"
        )
        advice.append(
            "Brain does not place orders — operator remains accountable"
        )

    if inp.news_blackout is True:
        advice.append("Respect news blackout — do not override")
    if inp.kill_switch is True:
        advice.append("Kill switch active — no trading activity")
    soft = config.max_open_positions_soft
    if inp.open_positions is not None and inp.open_positions >= soft:
        advice.append(
            f"Open positions ({inp.open_positions}) at soft limit {soft}"
        )
    if inp.operator_notes:
        for note in inp.operator_notes[:5]:
            advice.append(f"Operator note: {note}")

    # Surface top module reasons (explainable).
    for reason in module_reasons[:4]:
        if reason not in advice:
            advice.append(reason)

    advice.append("Never promises profitability; losses cannot be eliminated")
    advice.append("Thresholds remain configurable in policies")

    return ModuleResult(
        module="operator_advisor",
        status="available",
        score=None,
        passed=recommendation != "No Trade",
        recommendation=recommendation,
        reasons=tuple(advice),
        details={
            "brain_recommendation": recommendation,
            "uses_existing_pipeline": True,
            "alternate_execution_path": False,
        },
    )
