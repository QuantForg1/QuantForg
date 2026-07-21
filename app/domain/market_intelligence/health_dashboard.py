"""AI Health Dashboard — decision / execution / risk / reliability scores."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_intelligence.config import MarketIntelligenceConfig


@dataclass(frozen=True, slots=True)
class AiHealthInput:
    """Caller-supplied 0-100 scores from real analytics; None = unavailable."""

    decision_quality: Decimal | None = None
    execution_success: Decimal | None = None
    risk_discipline: Decimal | None = None
    system_reliability: Decimal | None = None


@dataclass(frozen=True, slots=True)
class AiHealthDashboard:
    decision_quality: Decimal | None
    execution_success: Decimal | None
    risk_discipline: Decimal | None
    system_reliability: Decimal | None
    overall: Decimal | None
    healthy: bool
    status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_quality": (
                str(self.decision_quality)
                if self.decision_quality is not None
                else None
            ),
            "execution_success": (
                str(self.execution_success)
                if self.execution_success is not None
                else None
            ),
            "risk_discipline": (
                str(self.risk_discipline)
                if self.risk_discipline is not None
                else None
            ),
            "system_reliability": (
                str(self.system_reliability)
                if self.system_reliability is not None
                else None
            ),
            "overall": str(self.overall) if self.overall is not None else None,
            "healthy": self.healthy,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def build_ai_health_dashboard(
    config: MarketIntelligenceConfig, inp: AiHealthInput
) -> AiHealthDashboard:
    values = [
        inp.decision_quality,
        inp.execution_success,
        inp.risk_discipline,
        inp.system_reliability,
    ]
    present = [v for v in values if v is not None]
    if not present:
        return AiHealthDashboard(
            decision_quality=None,
            execution_success=None,
            risk_discipline=None,
            system_reliability=None,
            overall=None,
            healthy=False,
            status="unavailable",
            reasons=(
                "No AI health metrics supplied — empty dashboard; "
                "never invent success rates.",
            ),
        )

    overall = (
        sum(present, Decimal("0")) / Decimal(len(present))
    ).quantize(Decimal("0.01"))
    reasons: list[str] = []
    healthy = True

    checks = [
        ("decision_quality", inp.decision_quality, config.min_decision_quality),
        ("execution_success", inp.execution_success, config.min_execution_success),
        ("risk_discipline", inp.risk_discipline, config.min_risk_discipline),
        (
            "system_reliability",
            inp.system_reliability,
            config.min_system_reliability,
        ),
    ]
    for name, value, minimum in checks:
        if value is None:
            reasons.append(f"{name} unavailable.")
            continue
        if value < minimum:
            healthy = False
            reasons.append(f"{name} {value} below min {minimum}.")
        else:
            reasons.append(f"{name} {value} ok.")

    reasons.append(f"Overall AI health {overall} from {len(present)} metrics.")
    return AiHealthDashboard(
        decision_quality=inp.decision_quality,
        execution_success=inp.execution_success,
        risk_discipline=inp.risk_discipline,
        system_reliability=inp.system_reliability,
        overall=overall,
        healthy=healthy,
        status="available",
        reasons=tuple(reasons),
    )
