"""Research promotion state machine — NEVER auto APPROVED_FOR_LIVE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class PromotionState(str, Enum):
    RESEARCH = "RESEARCH"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    SHADOW = "SHADOW"
    SHADOW_FAILED = "SHADOW_FAILED"
    SHADOW_PASSED = "SHADOW_PASSED"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    APPROVED_FOR_LIVE = "APPROVED_FOR_LIVE"
    DEPLOYED = "DEPLOYED"


# Automatic transitions allowed without human approval
_AUTO_ALLOWED = {
    PromotionState.RESEARCH: {
        PromotionState.VALIDATION_FAILED,
        PromotionState.VALIDATION_PASSED,
    },
    PromotionState.VALIDATION_PASSED: {PromotionState.SHADOW},
    PromotionState.SHADOW: {
        PromotionState.SHADOW_FAILED,
        PromotionState.SHADOW_PASSED,
    },
    PromotionState.SHADOW_PASSED: {PromotionState.PROMOTION_REVIEW},
}

# Require explicit approval record
_APPROVAL_REQUIRED = {
    PromotionState.PROMOTION_REVIEW: {
        PromotionState.APPROVED_FOR_LIVE,
    },
    PromotionState.APPROVED_FOR_LIVE: {PromotionState.DEPLOYED},
}


@dataclass
class PromotionCandidate:
    candidate_id: str
    strategy_id: str
    research_run_id: str
    state: PromotionState
    blocking_reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    approval_actor: str | None = None
    approval_timestamp: str | None = None
    approval_note: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "strategy_id": self.strategy_id,
            "research_run_id": self.research_run_id,
            "state": self.state.value,
            "blocking_reason": self.blocking_reason,
            "evidence": dict(self.evidence),
            "approval_actor": self.approval_actor,
            "approval_timestamp": self.approval_timestamp,
            "approval_note": self.approval_note,
            "history": list(self.history),
            "auto_approved": False,
        }


@dataclass
class PromotionStateMachine:
    candidates: dict[str, PromotionCandidate] = field(default_factory=dict)
    auto_approve_for_live: bool = False  # hard False
    _lock: RLock = field(default_factory=RLock, repr=False)

    def register(
        self,
        *,
        strategy_id: str,
        research_run_id: str,
        candidate_id: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> PromotionCandidate:
        cid = str(candidate_id or uuid4())
        cand = PromotionCandidate(
            candidate_id=cid,
            strategy_id=str(strategy_id),
            research_run_id=str(research_run_id),
            state=PromotionState.RESEARCH,
            evidence=dict(evidence or {}),
            history=[
                {
                    "to": PromotionState.RESEARCH.value,
                    "at": datetime.now(UTC).isoformat(),
                    "actor": "system",
                }
            ],
        )
        with self._lock:
            self.candidates[cid] = cand
        return cand

    def transition(
        self,
        candidate_id: str,
        to_state: PromotionState | str,
        *,
        actor: str = "system",
        note: str | None = None,
        evidence: dict[str, Any] | None = None,
        blocking_reason: str | None = None,
    ) -> PromotionCandidate:
        target = (
            to_state
            if isinstance(to_state, PromotionState)
            else PromotionState(str(to_state))
        )
        with self._lock:
            cand = self.candidates[candidate_id]
            allowed_auto = _AUTO_ALLOWED.get(cand.state, set())
            needs_approval = target in _APPROVAL_REQUIRED.get(cand.state, set())

            if needs_approval:
                if self.auto_approve_for_live:
                    raise RuntimeError("auto_approve_for_live is forbidden in Phase C")
                if actor in {"system", "auto", ""}:
                    cand.blocking_reason = (
                        blocking_reason
                        or "EXPLICIT_APPROVAL_REQUIRED"
                    )
                    raise PermissionError(
                        "APPROVED_FOR_LIVE / DEPLOYED requires explicit approval actor"
                    )
                cand.approval_actor = actor
                cand.approval_timestamp = datetime.now(UTC).isoformat()
                cand.approval_note = note
            elif target not in allowed_auto and target != cand.state:
                # Allow failure transitions from review only with actor
                if target in {
                    PromotionState.VALIDATION_FAILED,
                    PromotionState.SHADOW_FAILED,
                }:
                    pass
                else:
                    raise ValueError(
                        f"Illegal transition {cand.state.value} → {target.value}"
                    )

            cand.state = target
            cand.blocking_reason = blocking_reason
            if evidence:
                cand.evidence.update(evidence)
            cand.history.append(
                {
                    "to": target.value,
                    "at": datetime.now(UTC).isoformat(),
                    "actor": actor,
                    "note": note,
                }
            )
            return cand

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [c.to_dict() for c in self.candidates.values()]
        return {
            "auto_approve_for_live": False,
            "candidates": rows[-50:],
            "count": len(rows),
        }
