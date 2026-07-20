"""Certification dashboard scores + production readiness."""

from __future__ import annotations

from app.domain.institutional_trading.certification.models import (
    CertificationEvidence,
    GateRequirement,
    Scorecard,
    StageCheck,
    StressBatchResult,
    FailureInjectionResult,
)


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, float(v)))


class CertificationDashboard:
    """Compute overall engine scorecard from certification evidence."""

    def score(
        self,
        evidence: CertificationEvidence,
        *,
        stage_checks: list[StageCheck],
        gate: list[GateRequirement],
        stress: list[StressBatchResult],
        failures: list[FailureInjectionResult],
    ) -> Scorecard:
        stage_pct = (
            100.0 * sum(1 for s in stage_checks if s.passed) / len(stage_checks)
            if stage_checks
            else 0.0
        )
        gate_pct = (
            100.0 * sum(1 for g in gate if g.passed) / len(gate) if gate else 0.0
        )
        stress_pct = (
            100.0 * sum(1 for s in stress if s.passed) / len(stress) if stress else 0.0
        )
        fail_pct = (
            100.0 * sum(1 for f in failures if f.graceful) / len(failures)
            if failures
            else 0.0
        )

        reliability = _clamp(
            0.5 * evidence.reliability_score
            + 0.3 * fail_pct
            + 0.2 * (evidence.gateway_uptime_pct)
        )
        execution = _clamp(
            0.5 * evidence.execution_score
            + 0.3 * evidence.canary.execution_success_pct
            + 0.2
            * (
                100.0
                if evidence.canary.duplicate_executions == 0
                else 0.0
            )
        )
        research = _clamp(evidence.research_score)
        risk = _clamp(
            evidence.risk_score
            if evidence.critical_incidents == 0
            else evidence.risk_score * 0.5
        )
        operations = _clamp(
            0.6 * evidence.operations_score + 0.4 * gate_pct
        )
        overall = _clamp(
            0.25 * stage_pct
            + 0.20 * reliability
            + 0.20 * execution
            + 0.10 * research
            + 0.10 * risk
            + 0.10 * operations
            + 0.05 * stress_pct
        )
        production_ready = (
            overall >= 90.0
            and all(s.passed for s in stage_checks)
            and all(g.passed for g in gate)
            and all(f.graceful for f in failures)
            and evidence.critical_incidents == 0
            and evidence.canary.duplicate_executions == 0
        )
        return Scorecard(
            overall=overall,
            reliability=reliability,
            execution=execution,
            research=research,
            risk=risk,
            operations=operations,
            production_ready=production_ready,
        )
