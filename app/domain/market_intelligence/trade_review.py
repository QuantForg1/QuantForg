"""AI trade review — explain accept/reject with strengths and weaknesses."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.market_intelligence.consensus import ConsensusResult
from app.domain.market_intelligence.execution_quality import ExecutionQualityReview
from app.domain.market_intelligence.opportunity import OpportunityRanking
from app.domain.market_intelligence.regime import RegimeAssessment


@dataclass(frozen=True, slots=True)
class AiTradeReview:
    accepted: bool
    summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    operator_summary: str
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "summary": self.summary,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "operator_summary": self.operator_summary,
            "disclaimer": self.disclaimer,
        }


def build_ai_trade_review(
    *,
    gate_open: bool,
    regime: RegimeAssessment,
    consensus: ConsensusResult,
    opportunities: OpportunityRanking,
    execution: ExecutionQualityReview,
    risk_passed: bool | None,
    safety_passed: bool | None,
) -> AiTradeReview:
    strengths: list[str] = []
    weaknesses: list[str] = []

    if regime.status == "available":
        strengths.append(f"Regime classified: {regime.primary.value}.")
        strengths.extend(regime.evidence[:2])
    else:
        weaknesses.append(regime.reason)

    if consensus.accepted:
        strengths.extend(consensus.reasons)
    else:
        weaknesses.extend(consensus.reasons)

    if opportunities.eligible:
        strengths.append(
            f"{len(opportunities.eligible)} opportunities above threshold."
        )
    else:
        weaknesses.extend(opportunities.reasons)

    if execution.passed:
        strengths.append(f"Execution quality overall {execution.overall}.")
    else:
        weaknesses.extend(execution.reasons[:3])

    if risk_passed is True:
        strengths.append("Risk Engine ALLOW supplied.")
    elif risk_passed is False:
        weaknesses.append("Risk Engine did not ALLOW.")
    else:
        weaknesses.append("Risk Engine not assessed — fail closed.")

    if safety_passed is True:
        strengths.append("Safety Engine ALLOW supplied.")
    elif safety_passed is False:
        weaknesses.append("Safety Engine did not ALLOW.")
    else:
        weaknesses.append("Safety Engine not assessed — fail closed.")

    accepted = gate_open
    summary = (
        "Trade path accepted for operator review (advisory / pre-submit only)."
        if accepted
        else "Trade path rejected — capital preservation / discipline gates."
    )
    operator_summary = (
        f"{'ACCEPT' if accepted else 'REJECT'}: "
        f"regime={regime.primary.value}; "
        f"consensus={'ok' if consensus.accepted else 'block'}; "
        f"eligible_ops={len(opportunities.eligible)}; "
        f"exec_quality={execution.overall if execution.overall is not None else 'n/a'}."
    )
    return AiTradeReview(
        accepted=accepted,
        summary=summary,
        strengths=tuple(strengths[:8]),
        weaknesses=tuple(weaknesses[:8]),
        operator_summary=operator_summary,
        disclaimer=(
            "AI Trade Review explains process discipline only. "
            "It is not a profitability promise. Live orders must still pass "
            "Risk Engine and Safety Engine via the unchanged execution pipeline. "
            "Market Intelligence V1 never calls order_send."
        ),
    )
