"""Production Certification Workflow — compose certification payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OPERATOR_CHECKLIST: tuple[str, ...] = (
    "Confirm XAUUSD-only configuration",
    "Confirm Risk Engine assessed (never bypassed)",
    "Confirm Safety Engine assessed (never bypassed)",
    "Confirm kill switch posture reviewed",
    "Confirm SHADOW to CANARY to LIVE human promotion path",
    "Confirm kernel replay/audit trail healthy",
    "Confirm plugins isolated (no order_send)",
    "Confirm execution architecture unchanged",
)


@dataclass(frozen=True, slots=True)
class CertificationWorkflowResult:
    status: str
    go_nogo: str | None
    checklist: list[dict[str, Any]]
    certification: dict[str, Any] | None
    auto_promote: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "go_nogo": self.go_nogo,
            "checklist": list(self.checklist),
            "certification": self.certification,
            "auto_promote": False,
            "detail": self.detail,
            "never_order_send": True,
            "human_gate_required": True,
        }


def build_certification_workflow(
    certification: dict[str, Any] | None,
    *,
    go_nogo: str | None = None,
) -> CertificationWorkflowResult:
    if certification is None and go_nogo is None:
        return CertificationWorkflowResult(
            status="unavailable",
            go_nogo=None,
            checklist=[
                {"step": i + 1, "text": t, "done": False}
                for i, t in enumerate(OPERATOR_CHECKLIST)
            ],
            certification=None,
            auto_promote=False,
            detail="Certification feed unavailable",
        )
    status_val = go_nogo or (
        str(certification.get("go_nogo")) if certification else None
    )
    return CertificationWorkflowResult(
        status="available",
        go_nogo=status_val,
        checklist=[
            {"step": i + 1, "text": t, "done": False}
            for i, t in enumerate(OPERATOR_CHECKLIST)
        ],
        certification=dict(certification) if certification else None,
        auto_promote=False,
        detail="Human gate required — kernel never auto-promotes LIVE",
    )
