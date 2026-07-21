"""Confidence voting across agent outputs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.multi_agent_ai.config import MultiAgentConfig
from app.domain.multi_agent_ai.types import AgentOutput, Vote


@dataclass(frozen=True, slots=True)
class VoteTally:
    decision: Vote
    approve_weight: Decimal
    hold_weight: Decimal
    reject_weight: Decimal
    abstain_count: int
    quorum_met: bool
    min_confidence_met: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "approve_weight": str(self.approve_weight),
            "hold_weight": str(self.hold_weight),
            "reject_weight": str(self.reject_weight),
            "abstain_count": self.abstain_count,
            "quorum_met": self.quorum_met,
            "min_confidence_met": self.min_confidence_met,
            "reasons": list(self.reasons),
        }


def tally_votes(
    outputs: list[AgentOutput], config: MultiAgentConfig
) -> VoteTally:
    approve = Decimal("0")
    hold = Decimal("0")
    reject = Decimal("0")
    abstain = 0
    active = 0
    reasons: list[str] = []

    for out in outputs:
        if out.vote == "ABSTAIN" or out.status == "unavailable":
            abstain += 1
            continue
        active += 1
        weight = out.confidence
        # Authoritative agents (Risk/Safety) get amplified weight.
        if out.authoritative:
            weight = weight * Decimal("1.5")
        if out.vote == "APPROVE":
            approve += weight
        elif out.vote == "REJECT":
            reject += weight
        else:
            hold += weight

    quorum_met = active >= config.quorum_agents
    total = approve + hold + reject
    avg_conf = (total / Decimal(str(active))) if active else Decimal("0")
    min_conf_met = avg_conf >= config.min_vote_confidence if active else False

    # Any authoritative REJECT wins.
    for out in outputs:
        if out.authoritative and out.vote == "REJECT":
            reasons.append(f"Authoritative {out.agent} REJECT overrides")
            return VoteTally(
                decision="REJECT",
                approve_weight=approve,
                hold_weight=hold,
                reject_weight=reject,
                abstain_count=abstain,
                quorum_met=quorum_met,
                min_confidence_met=min_conf_met,
                reasons=tuple(reasons),
            )
        if out.authoritative and out.vote == "HOLD" and out.status == "unavailable":
            reasons.append(f"Authoritative {out.agent} unavailable — HOLD")
            return VoteTally(
                decision="HOLD",
                approve_weight=approve,
                hold_weight=hold,
                reject_weight=reject,
                abstain_count=abstain,
                quorum_met=quorum_met,
                min_confidence_met=min_conf_met,
                reasons=tuple(reasons),
            )

    if not quorum_met:
        reasons.append(
            f"Quorum not met ({active}/{config.quorum_agents}) — HOLD"
        )
        decision: Vote = "HOLD"
    elif reject >= approve and reject >= hold and reject > 0:
        decision = "REJECT"
        reasons.append("Reject weight leads confidence vote")
    elif approve > hold and approve > reject and min_conf_met:
        decision = "APPROVE"
        reasons.append("Approve weight leads with min confidence met")
    else:
        decision = "HOLD"
        reasons.append("Hold by confidence vote / insufficient confidence")

    return VoteTally(
        decision=decision,
        approve_weight=approve,
        hold_weight=hold,
        reject_weight=reject,
        abstain_count=abstain,
        quorum_met=quorum_met,
        min_confidence_met=min_conf_met,
        reasons=tuple(reasons),
    )
