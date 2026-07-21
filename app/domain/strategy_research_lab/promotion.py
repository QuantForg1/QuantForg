"""Promotion workflow, operator approval, and promotion dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.domain.strategy_research_lab.config import StrategyLabConfig
from app.domain.strategy_research_lab.scorecards import StrategyScorecard


class PromotionState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"  # eligible for DE review only — not live


@dataclass(frozen=True, slots=True)
class OperatorApproval:
    approval_id: str
    strategy_key: str
    decision: str  # approve | reject
    operator: str
    reason: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "approval_id": self.approval_id,
            "strategy_key": self.strategy_key,
            "decision": self.decision,
            "operator": self.operator,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "lab_only": True,
            "never_submits_orders": True,
        }


@dataclass
class PromotionCase:
    case_id: str
    strategy_key: str
    state: PromotionState
    scorecard: dict[str, object]
    validation_passed: bool
    created_at: datetime
    updated_at: datetime
    approvals: list[OperatorApproval] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "strategy_key": self.strategy_key,
            "state": self.state.value,
            "scorecard": dict(self.scorecard),
            "validation_passed": self.validation_passed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "approvals": [a.to_dict() for a in self.approvals],
            "notes": self.notes,
            "forwarded_to_live_execution": False,
            "decision_engine_gatekeeper": True,
        }


class PromotionWorkflow:
    def __init__(self, config: StrategyLabConfig) -> None:
        self.config = config
        self._cases: dict[str, PromotionCase] = {}

    def open_case(
        self,
        *,
        strategy_key: str,
        scorecard: StrategyScorecard,
        validation_passed: bool,
        notes: str = "",
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        state = PromotionState.PENDING_APPROVAL
        if self.config.require_scorecard_pass and not scorecard.passed:
            state = PromotionState.REJECTED
        if self.config.require_validation_pass and not validation_passed:
            state = PromotionState.REJECTED

        case = PromotionCase(
            case_id=str(uuid4()),
            strategy_key=strategy_key,
            state=state,
            scorecard=scorecard.to_dict(),
            validation_passed=validation_passed,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        self._cases[case.case_id] = case
        return case.to_dict()

    def operator_decide(
        self,
        *,
        case_id: str,
        decision: str,
        operator: str,
        reason: str = "",
    ) -> dict[str, object] | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        if case.state not in {
            PromotionState.PENDING_APPROVAL,
            PromotionState.DRAFT,
        }:
            return case.to_dict()

        decision_l = decision.strip().lower()
        approval = OperatorApproval(
            approval_id=str(uuid4()),
            strategy_key=case.strategy_key,
            decision=decision_l,
            operator=operator,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        case.approvals.append(approval)
        case.updated_at = datetime.now(UTC)

        if decision_l == "approve":
            case.state = PromotionState.PROMOTED
            case.notes = (
                (case.notes + " | " if case.notes else "")
                + "Promoted to Decision Engine eligibility only — not live."
            )
        elif decision_l == "reject":
            case.state = PromotionState.REJECTED
        return case.to_dict()

    def list_cases(self) -> list[dict[str, object]]:
        rows = sorted(
            self._cases.values(), key=lambda c: c.updated_at, reverse=True
        )
        return [c.to_dict() for c in rows]

    def dashboard(self) -> dict[str, Any]:
        cases = self.list_cases()
        by_state: dict[str, int] = {}
        for c in cases:
            st = str(c["state"])
            by_state[st] = by_state.get(st, 0) + 1
        pending = [c for c in cases if c["state"] == "pending_approval"]
        promoted = [c for c in cases if c["state"] == "promoted"]
        return {
            "counts_by_state": by_state,
            "pending_approvals": pending[:20],
            "promoted": promoted[:20],
            "recent": cases[:20],
            "note": (
                "Promotion Dashboard is lab-only. Promoted means eligible for "
                "Decision Engine review — never auto-submits broker orders."
            ),
            "isolation": {
                "separated_from_live_execution": True,
                "never_order_send": True,
            },
        }
