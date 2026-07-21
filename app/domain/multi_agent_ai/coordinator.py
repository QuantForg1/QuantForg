"""Decision Coordinator — may reject/HOLD; never bypasses Risk or Safety."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.multi_agent_ai.config import MultiAgentConfig
from app.domain.multi_agent_ai.events import AgentEventBus
from app.domain.multi_agent_ai.governance import evaluate_governance
from app.domain.multi_agent_ai.types import AgentOutput, CollaborationInput
from app.domain.multi_agent_ai.voting import VoteTally, tally_votes


@dataclass(frozen=True, slots=True)
class CoordinatorDecision:
    decision: str
    allow_execution_path: bool
    advisory_only: bool
    reasons: tuple[str, ...]
    vote_tally: VoteTally
    governance_passed: bool
    bypasses_risk: bool
    bypasses_safety: bool
    never_order_send: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "allow_execution_path": self.allow_execution_path,
            "advisory_only": True,
            "reasons": list(self.reasons),
            "vote_tally": self.vote_tally.to_dict(),
            "governance_passed": self.governance_passed,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "never_order_send": True,
            "execution_pipeline_unchanged": True,
            "risk_engine_authoritative": True,
            "safety_engine_authoritative": True,
        }


def coordinate(
    *,
    inp: CollaborationInput,
    outputs: list[AgentOutput],
    config: MultiAgentConfig,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> CoordinatorDecision:
    tally = tally_votes(outputs, config)
    reasons: list[str] = list(tally.reasons)

    decision = tally.decision

    # Hard fail-closed on Risk / Safety — coordinator never bypasses.
    if inp.risk_engine_passed is False:
        decision = "REJECT"
        reasons.append(
            "Coordinator enforces Risk Engine authority — no bypass"
        )
    elif inp.risk_engine_passed is None:
        decision = "HOLD"
        reasons.append(
            "Coordinator enforces Risk Engine authority — no bypass"
        )

    if inp.safety_engine_passed is False:
        decision = "REJECT"
        reasons.append(
            "Coordinator enforces Safety Engine authority — no bypass"
        )
    elif inp.safety_engine_passed is None and decision == "APPROVE":
        decision = "HOLD"
        reasons.append(
            "Coordinator enforces Safety Engine authority — no bypass"
        )
    elif inp.safety_engine_passed is None:
        reasons.append(
            "Coordinator enforces Safety Engine authority — no bypass"
        )

    # APPROVE is advisory only — never triggers execution pipeline.
    allow = decision == "APPROVE"
    if allow:
        reasons.append("APPROVE is advisory — never order_send")

    gov = evaluate_governance(
        config=config,
        outputs=outputs,
        decision=decision,
        allow_execution_path=allow,
        risk_engine_passed=inp.risk_engine_passed,
        safety_engine_passed=inp.safety_engine_passed,
    )
    if not gov.passed:
        decision = "HOLD" if decision == "APPROVE" else decision
        allow = False
        reasons.extend(gov.violations)
        reasons.append("Governance fail-closed")

    result = CoordinatorDecision(
        decision=decision,
        allow_execution_path=allow,
        advisory_only=True,
        reasons=tuple(reasons),
        vote_tally=tally,
        governance_passed=gov.passed,
        bypasses_risk=False,
        bypasses_safety=False,
        never_order_send=True,
    )
    if bus is not None:
        bus.publish(
            event_type="coordinator.decided",
            agent="coordinator",
            payload=result.to_dict(),
            session_id=session_id,
        )
    return result
