"""Live acceptance gate — promotion to LIVE only when thresholds met."""

from __future__ import annotations

from app.domain.institutional_trading.certification.models import (
    CANARY_MIN_TRADES,
    CRITICAL_INCIDENTS_MAX,
    DUPLICATE_EXECUTIONS_MAX,
    EXECUTION_SUCCESS_MIN_PCT,
    GATEWAY_UPTIME_MIN_PCT,
    SHADOW_MIN_DAYS,
    CanaryMetrics,
    CertificationEvidence,
    GateRequirement,
)


class LiveAcceptanceGate:
    """Hard gates for LIVE promotion. Measurement only — does not change mode."""

    def evaluate(self, evidence: CertificationEvidence) -> list[GateRequirement]:
        c = evidence.canary
        return [
            GateRequirement(
                name="shadow_days",
                required=f">={SHADOW_MIN_DAYS}",
                actual=str(evidence.shadow_days),
                passed=evidence.shadow_days >= SHADOW_MIN_DAYS,
            ),
            GateRequirement(
                name="canary_trades",
                required=f">={CANARY_MIN_TRADES}",
                actual=str(c.total_trades),
                passed=c.total_trades >= CANARY_MIN_TRADES,
            ),
            GateRequirement(
                name="gateway_uptime_pct",
                required=f">={GATEWAY_UPTIME_MIN_PCT}",
                actual=str(evidence.gateway_uptime_pct),
                passed=evidence.gateway_uptime_pct >= GATEWAY_UPTIME_MIN_PCT,
            ),
            GateRequirement(
                name="execution_success_pct",
                required=f">={EXECUTION_SUCCESS_MIN_PCT}",
                actual=str(c.execution_success_pct),
                passed=c.execution_success_pct >= EXECUTION_SUCCESS_MIN_PCT,
            ),
            GateRequirement(
                name="duplicate_executions",
                required=f"=={DUPLICATE_EXECUTIONS_MAX}",
                actual=str(c.duplicate_executions),
                passed=c.duplicate_executions == DUPLICATE_EXECUTIONS_MAX,
            ),
            GateRequirement(
                name="critical_incidents",
                required=f"=={CRITICAL_INCIDENTS_MAX}",
                actual=str(evidence.critical_incidents),
                passed=evidence.critical_incidents == CRITICAL_INCIDENTS_MAX,
            ),
        ]

    def passed(self, evidence: CertificationEvidence) -> bool:
        return all(g.passed for g in self.evaluate(evidence))

    def failed_names(self, evidence: CertificationEvidence) -> list[str]:
        return [g.name for g in self.evaluate(evidence) if not g.passed]

    @staticmethod
    def from_canary_and_ops(
        *,
        shadow_days: float,
        canary: CanaryMetrics,
        gateway_uptime_pct: float,
        critical_incidents: int,
    ) -> list[GateRequirement]:
        return LiveAcceptanceGate().evaluate(
            CertificationEvidence(
                shadow_days=shadow_days,
                canary=canary,
                gateway_uptime_pct=gateway_uptime_pct,
                critical_incidents=critical_incidents,
            )
        )
