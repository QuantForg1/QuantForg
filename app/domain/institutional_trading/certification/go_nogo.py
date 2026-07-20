"""Go / No-Go engine — single promotion verdict with failed requirement explanations."""

from __future__ import annotations

from app.domain.institutional_trading.certification.models import (
    CertificationEvidence,
    FailureInjectionResult,
    GateRequirement,
    GoNoGoStatus,
    StageCheck,
    StressBatchResult,
)


class GoNoGoEngine:
    """
    NOT READY | READY FOR CANARY | READY FOR LIVE

    LIVE requires full gate + E2E + failure graceful + stress pass.
    CANARY requires E2E pipeline + stress + failures graceful (gate may be partial).
    """

    def evaluate(
        self,
        *,
        stage_checks: list[StageCheck],
        gate: list[GateRequirement],
        stress: list[StressBatchResult],
        failures: list[FailureInjectionResult],
        evidence: CertificationEvidence,
    ) -> tuple[GoNoGoStatus, list[str]]:
        failed: list[str] = []

        for s in stage_checks:
            if not s.passed:
                failed.append(f"pipeline:{s.stage.value} — {s.detail}")

        for st in stress:
            if not st.passed:
                failed.append(
                    f"stress:batch_{st.batch_size} — {st.detail or 'failed'}"
                )

        for f in failures:
            if not f.graceful:
                failed.append(
                    f"failure_injection:{f.scenario.value} — {f.detail}"
                )

        if evidence.critical_incidents > 0:
            failed.append(
                f"critical_incidents — actual={evidence.critical_incidents} required=0"
            )

        pipeline_ok = all(s.passed for s in stage_checks)
        stress_ok = all(s.passed for s in stress) if stress else False
        failures_ok = all(f.graceful for f in failures) if failures else False
        base_ok = pipeline_ok and stress_ok and failures_ok

        gate_failed = [g for g in gate if not g.passed]
        for g in gate_failed:
            failed.append(
                f"live_gate:{g.name} — required {g.required}, actual {g.actual}"
            )

        live_ok = base_ok and not gate_failed and evidence.canary.duplicate_executions == 0

        if live_ok:
            return GoNoGoStatus.READY_FOR_LIVE, []

        if base_ok:
            # Ready for canary even if live gates not met — explain live blockers only
            live_blockers = [
                f
                for f in failed
                if f.startswith("live_gate:") or f.startswith("critical_incidents")
            ]
            return GoNoGoStatus.READY_FOR_CANARY, live_blockers

        return GoNoGoStatus.NOT_READY, failed
