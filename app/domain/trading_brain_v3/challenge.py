"""Decision Challenge — stress-test vs Decision Center / Risk / Safety facts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def run_decision_challenge(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    reasons: list[str] = []
    score = Decimal("50")
    details: dict[str, Any] = {}

    dc = inp.decision_center
    if (
        dc is None
        and inp.risk_engine_passed is None
        and inp.safety_engine_passed is None
    ):
        return ModuleResult(
            module="decision_challenge",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No Decision Center or Risk/Safety facts — cannot challenge",
                "Uses existing Decision Center / engines when supplied",
            ),
            details={},
        )

    if isinstance(dc, dict):
        details["decision_center_present"] = True
        decision = str(dc.get("decision") or "").upper()
        details["decision_center_decision"] = decision or None
        if decision == "REJECT":
            score = Decimal("10")
            reasons.append("Decision Center REJECT — challenge fails")
        elif decision == "HOLD":
            score = Decimal("40")
            reasons.append("Decision Center HOLD — challenge cautious")
        elif decision == "APPROVE":
            score = Decimal("75")
            reasons.append("Decision Center APPROVE observed (external)")
        else:
            reasons.append("Decision Center payload present without clear decision")
        if dc.get("allow_execution_path") is True:
            reasons.append("Decision Center allow_execution_path noted (advisory)")
    else:
        details["decision_center_present"] = False
        reasons.append("Decision Center payload absent — using Risk/Safety facts")

    if inp.risk_engine_passed is False:
        score = min(score, Decimal("15"))
        reasons.append("Risk Engine failed — challenge veto (authoritative)")
    elif inp.risk_engine_passed is True:
        score += Decimal("10")
        reasons.append("Risk Engine passed (existing engine, unchanged)")
    else:
        score = min(score, Decimal("35"))
        reasons.append("Risk Engine not assessed — fail closed")

    if inp.safety_engine_passed is False:
        score = min(score, Decimal("15"))
        reasons.append("Safety Engine failed — challenge veto (authoritative)")
    elif inp.safety_engine_passed is True:
        score += Decimal("10")
        reasons.append("Safety Engine passed (existing engine, unchanged)")
    else:
        score = min(score, Decimal("35"))
        reasons.append("Safety Engine not assessed — fail closed")

    if inp.kill_switch is True:
        score = Decimal("0")
        reasons.append("Kill switch — challenge hard fail")

    score = min(score, Decimal("100")).quantize(Decimal("0.01"))
    passed = (
        score >= config.min_challenge_pass_score
        and inp.risk_engine_passed is True
        and inp.safety_engine_passed is True
        and inp.kill_switch is not True
    )
    return ModuleResult(
        module="decision_challenge",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=(
            *reasons,
            f"Challenge score {score} vs min {config.min_challenge_pass_score}",
            "Never bypasses Risk or Safety; no alternate execution path",
        ),
        details={
            **details,
            "risk_engine_passed": inp.risk_engine_passed,
            "safety_engine_passed": inp.safety_engine_passed,
            "min_challenge_pass_score": str(config.min_challenge_pass_score),
        },
    )
