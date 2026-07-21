"""Explainable AI decision summary + executive panel payload."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.decision_intelligence.confidence import ConfidenceBreakdown
from app.domain.decision_intelligence.veto import VetoResult
from app.domain.decision_intelligence.waterfall import WaterfallStage


@dataclass(frozen=True, slots=True)
class ExplainableSummary:
    decision: str  # APPROVE | REJECT | HOLD
    headline: str
    why_approved: tuple[str, ...]
    why_rejected: tuple[str, ...]
    operator_summary: str
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "headline": self.headline,
            "why_approved": list(self.why_approved),
            "why_rejected": list(self.why_rejected),
            "operator_summary": self.operator_summary,
            "disclaimer": self.disclaimer,
        }


def build_explainable_summary(
    *,
    decision: str,
    stages: tuple[WaterfallStage, ...],
    confidence: ConfidenceBreakdown,
    veto: VetoResult,
) -> ExplainableSummary:
    why_ok = [s.reason for s in stages if s.passed]
    why_no = [s.reason for s in stages if s.required and not s.passed]
    if not veto.clear:
        why_no.extend(veto.vetoes)
    if not confidence.passed:
        why_no.extend(confidence.reasons)

    if decision == "APPROVE":
        headline = (
            "APPROVE (advisory) — Risk+Safety ALLOW observed; "
            "Decision Center does not place orders."
        )
    elif decision == "HOLD":
        headline = "HOLD — incomplete assessment; fail closed."
    else:
        headline = "REJECT — capital preservation / policy gate."

    return ExplainableSummary(
        decision=decision,
        headline=headline,
        why_approved=tuple(why_ok[:8]),
        why_rejected=tuple(why_no[:8]),
        operator_summary=(
            f"{decision}: confidence={confidence.score} ({confidence.band}); "
            f"veto_clear={veto.clear}; "
            f"stages_passed="
            f"{sum(1 for s in stages if s.passed)}/{len(stages)}."
        ),
        disclaimer=(
            "Explainable AI Decision Summary is process discipline only. "
            "Never promises profitability. Never bypasses Risk or Safety. "
            "Decision Center may reject but never force-executes."
        ),
    )


@dataclass(frozen=True, slots=True)
class ExecutivePanel:
    decision: str
    allow_execution_path: bool
    confidence: str
    risk_passed: bool | None
    safety_passed: bool | None
    veto_clear: bool
    audit_id: str
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "allow_execution_path": self.allow_execution_path,
            "confidence": self.confidence,
            "risk_passed": self.risk_passed,
            "safety_passed": self.safety_passed,
            "veto_clear": self.veto_clear,
            "audit_id": self.audit_id,
            "note": self.note,
            "never_force_execution": True,
        }
