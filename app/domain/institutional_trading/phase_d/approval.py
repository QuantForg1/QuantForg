"""Explicit LIVE promotion approval records — never automatic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


REQUIRED_APPROVAL = (
    "candidate_id",
    "old_champion",
    "new_candidate",
    "research_run_id",
    "evidence_summary",
    "risk_review",
    "execution_review",
    "canary_result",
    "approval_actor",
    "promotion_reason",
)


@dataclass
class PromotionApproval:
    approval_id: str
    candidate_id: str
    old_champion: str
    new_candidate: str
    research_run_id: str
    evidence_summary: dict[str, Any]
    risk_review: str
    execution_review: str
    canary_result: str
    approval_actor: str
    approval_timestamp: str
    promotion_reason: str
    state: str  # APPROVED_FOR_LIVE | REJECTED
    auto_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "candidate_id": self.candidate_id,
            "old_champion": self.old_champion,
            "new_candidate": self.new_candidate,
            "research_run_id": self.research_run_id,
            "evidence_summary": dict(self.evidence_summary),
            "risk_review": self.risk_review,
            "execution_review": self.execution_review,
            "canary_result": self.canary_result,
            "approval_actor": self.approval_actor,
            "approval_timestamp": self.approval_timestamp,
            "promotion_reason": self.promotion_reason,
            "state": self.state,
            "auto_approved": False,
        }


@dataclass
class ApprovalStore:
    records: list[PromotionApproval] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def approve(self, **kwargs: Any) -> PromotionApproval:
        missing = [
            k
            for k in REQUIRED_APPROVAL
            if kwargs.get(k) is None or kwargs.get(k) == "" or kwargs.get(k) == {}
        ]
        actor = str(kwargs.get("approval_actor") or "")
        if missing:
            raise ValueError("incomplete approval: " + ",".join(missing))
        if actor in {"", "system", "auto"}:
            raise PermissionError("APPROVED_FOR_LIVE requires explicit human actor")
        rec = PromotionApproval(
            approval_id=str(kwargs.get("approval_id") or uuid4()),
            candidate_id=str(kwargs["candidate_id"]),
            old_champion=str(kwargs["old_champion"]),
            new_candidate=str(kwargs["new_candidate"]),
            research_run_id=str(kwargs["research_run_id"]),
            evidence_summary=dict(kwargs.get("evidence_summary") or {}),
            risk_review=str(kwargs["risk_review"]),
            execution_review=str(kwargs["execution_review"]),
            canary_result=str(kwargs["canary_result"]),
            approval_actor=actor,
            approval_timestamp=str(
                kwargs.get("approval_timestamp") or datetime.now(UTC).isoformat()
            ),
            promotion_reason=str(kwargs["promotion_reason"]),
            state="APPROVED_FOR_LIVE",
            auto_approved=False,
        )
        with self._lock:
            self.records.append(rec)
            if len(self.records) > 200:
                self.records = self.records[-200:]
        return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self.records]
        return {"count": len(rows), "recent": rows[-15:], "auto_approved": False}
