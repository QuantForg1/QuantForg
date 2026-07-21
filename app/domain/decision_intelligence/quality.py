"""Decision quality dashboard — supplied metrics only, never invented."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.decision_intelligence.config import DecisionIntelligenceConfig


@dataclass(frozen=True, slots=True)
class QualityInput:
    approve_precision: Decimal | None = None
    reject_precision: Decimal | None = None
    override_rate: Decimal | None = None
    audit_completeness: Decimal | None = None


@dataclass(frozen=True, slots=True)
class DecisionQualityDashboard:
    approve_precision: Decimal | None
    reject_precision: Decimal | None
    override_rate: Decimal | None
    audit_completeness: Decimal | None
    overall: Decimal | None
    healthy: bool
    status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "approve_precision": (
                str(self.approve_precision)
                if self.approve_precision is not None
                else None
            ),
            "reject_precision": (
                str(self.reject_precision)
                if self.reject_precision is not None
                else None
            ),
            "override_rate": (
                str(self.override_rate) if self.override_rate is not None else None
            ),
            "audit_completeness": (
                str(self.audit_completeness)
                if self.audit_completeness is not None
                else None
            ),
            "overall": str(self.overall) if self.overall is not None else None,
            "healthy": self.healthy,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def build_quality_dashboard(
    config: DecisionIntelligenceConfig, inp: QualityInput
) -> DecisionQualityDashboard:
    values = [
        inp.approve_precision,
        inp.reject_precision,
        inp.audit_completeness,
    ]
    # Lower override rate is better — invert if present
    if inp.override_rate is not None:
        values.append(Decimal("100") - inp.override_rate)

    present = [v for v in values if v is not None]
    if not present:
        return DecisionQualityDashboard(
            approve_precision=None,
            reject_precision=None,
            override_rate=None,
            audit_completeness=None,
            overall=None,
            healthy=False,
            status="unavailable",
            reasons=(
                "No decision quality metrics supplied — empty dashboard; "
                "never invent metrics.",
            ),
        )

    overall = (
        sum(present, Decimal("0")) / Decimal(len(present))
    ).quantize(Decimal("0.01"))
    healthy = overall >= config.min_decision_quality
    reasons = [
        f"Overall decision quality {overall} from {len(present)} supplied metrics."
    ]
    if not healthy:
        reasons.append(
            f"Below policy minimum {config.min_decision_quality}."
        )
    return DecisionQualityDashboard(
        approve_precision=inp.approve_precision,
        reject_precision=inp.reject_precision,
        override_rate=inp.override_rate,
        audit_completeness=inp.audit_completeness,
        overall=overall,
        healthy=healthy,
        status="available",
        reasons=tuple(reasons),
    )
